#!/usr/bin/env python3
"""
Duplicate File Finder
---------------------
Recursively scans the folder it lives in for duplicate filenames.
When duplicates are found, it verifies via file size then SHA-256 hash.
Only confirmed duplicates are acted on — the larger file is kept and
the smaller (or equal) is moved to 'duplicates-smaller_size'.
"""

import hashlib
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime


class Tee:
    """Writes output to both the terminal and a log file simultaneously."""
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", encoding="utf-8")  # "a" = append mode

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def get_exe_dir():
    """
    Returns the folder the .exe (or .py script) is actually running from.
    - When bundled by PyInstaller:  sys.executable points to the .exe
    - When run as a plain .py:      __file__ points to the script
    PyInstaller sets sys.frozen = True, so we use that to tell them apart.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        return os.path.dirname(os.path.abspath(__file__))


def sha256_hash(filepath):
    """
    Computes the SHA-256 hash of a file in 8MB chunks to handle
    large files (e.g. 1GB .mov) without loading them fully into memory.
    Prints progress every 256MB so the user knows it hasn't frozen.
    """
    h = hashlib.sha256()
    chunk_size = 8 * 1024 * 1024        # 8 MB per read
    progress_every = 256 * 1024 * 1024  # print progress every 256 MB
    bytes_read = 0
    last_reported = 0
    file_size = os.path.getsize(filepath)

    print(f"          🔍 Hashing: {os.path.basename(filepath)} ({file_size / (1024**3):.2f} GB)")

    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
            bytes_read += len(chunk)

            if bytes_read - last_reported >= progress_every:
                pct = (bytes_read / file_size) * 100
                print(f"              ... {pct:.0f}% ({bytes_read / (1024**3):.2f} GB / {file_size / (1024**3):.2f} GB)")
                last_reported = bytes_read

    print(f"              ... 100% — done")
    return h.hexdigest()


def _move_file(path, duplicates_dir):
    """
    Moves a file into the duplicates folder, handling name collisions.
    Returns the destination path on success, None on failure.
    """
    filename = os.path.basename(path)
    dest_name = filename
    dest_path = os.path.join(duplicates_dir, dest_name)

    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(dest_path):
        dest_name = f"{base}__{counter}{ext}"
        dest_path = os.path.join(duplicates_dir, dest_name)
        counter += 1

    try:
        shutil.move(path, dest_path)
        print(f"          → Moved to: {dest_path}")
        return dest_path
    except OSError as e:
        print(f"          ❌ Failed to move {path}: {e}")
        return None


def find_and_resolve_duplicates():
    script_dir = get_exe_dir()
    duplicates_dir = os.path.join(script_dir, "duplicates-smaller_size")

    # Single persistent log file, opened in append mode
    log_path = os.path.join(script_dir, "log.txt")
    tee = Tee(log_path)
    sys.stdout = tee

    # Separator so each run is clearly distinct inside the log
    print("\n" + "=" * 60)
    print(f"RUN — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"Scanning: {script_dir}\n")

    # --- Collect all files grouped by filename ---
    files_by_name: dict[str, list[str]] = defaultdict(list)

    exe_path = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None

    for dirpath, dirnames, filenames in os.walk(script_dir):
        # Skip the duplicates folder so we don't re-scan moved files
        dirnames[:] = [
            d for d in dirnames
            if os.path.join(dirpath, d) != duplicates_dir
        ]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            abs_path = os.path.abspath(full_path)

            # Skip the .exe itself
            if exe_path and abs_path == exe_path:
                continue
            # Skip the .py script (when running unpackaged)
            if not getattr(sys, "frozen", False) and abs_path == os.path.abspath(__file__):
                continue
            # Skip the log file
            if filename == "log-find_duplicates.txt":
                continue

            files_by_name[filename].append(full_path)

    # --- Identify filename duplicates ---
    duplicates_found = {name: paths for name, paths in files_by_name.items() if len(paths) > 1}

    if not duplicates_found:
        print("✅  No duplicate filenames found.")
        sys.stdout = tee.terminal
        tee.close()
        return

    print(f"Found {len(duplicates_found)} duplicate filename(s) — verifying each...\n")
    print("-" * 60)

    os.makedirs(duplicates_dir, exist_ok=True)

    # Track moves and skips for the final summary
    moved_files   = []   # list of (original_path, dest_path, size)
    skipped_files = []   # list of (path, reason)

    for filename, paths in duplicates_found.items():
        print(f"📄  '{filename}'  —  {len(paths)} copies found:")

        # --- Stage 1: Get file sizes ---
        sized = []
        for p in paths:
            try:
                sized.append((os.path.getsize(p), p))
            except OSError as e:
                print(f"     ⚠️  Could not read size for {p}: {e}")

        sized.sort(key=lambda x: x[0], reverse=True)

        keeper_size, keeper_path = sized[0]
        print(f"     ✅  KEEP   ({keeper_size:,} bytes)  {keeper_path}")

        for size, path in sized[1:]:
            print(f"     🔎  Checking ({size:,} bytes)  {path}")

            # --- Stage 2: Size differs → move immediately ---
            if size < keeper_size:
                print(f"          📏 Size differs from keeper — confirmed different file, moving.")
                dest = _move_file(path, duplicates_dir)
                if dest:
                    moved_files.append((path, dest, size))
                continue

            # --- Stage 3: Same size → SHA-256 hash to confirm ---
            print(f"          📏 Same size as keeper — running SHA-256 hash to confirm...")

            try:
                hash_keeper    = sha256_hash(keeper_path)
                hash_candidate = sha256_hash(path)
            except OSError as e:
                print(f"          ❌ Could not hash file: {e} — skipping.")
                skipped_files.append((path, "hashing error"))
                continue

            print(f"          Keeper hash:    {hash_keeper}")
            print(f"          Candidate hash: {hash_candidate}")

            if hash_keeper == hash_candidate:
                print(f"          ✅ Hashes MATCH — confirmed exact duplicate, moving.")
                dest = _move_file(path, duplicates_dir)
                if dest:
                    moved_files.append((path, dest, size))
            else:
                print(f"          ⚠️  Hashes DIFFER — files are NOT identical despite same name and size.")
                print(f"          ⏭️  Skipping — both files kept in place.")
                skipped_files.append((path, "same name & size but different content"))

        print()

    # ------------------------------------------------------------------ #
    #  FINAL SUMMARY
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if moved_files:
        print(f"\n📦  {len(moved_files)} file(s) moved to: {duplicates_dir}\n")
        for i, (original, dest, size) in enumerate(moved_files, 1):
            print(f"  {i:>3}.  {os.path.basename(original)}")
            print(f"        Original : {original}")
            print(f"        Moved to : {dest}")
            print(f"        Size     : {size:,} bytes")
            print()
    else:
        print("\n  No files were moved.")

    if skipped_files:
        print(f"⏭️  {len(skipped_files)} file(s) skipped:\n")
        for i, (path, reason) in enumerate(skipped_files, 1):
            print(f"  {i:>3}.  {os.path.basename(path)}")
            print(f"        Path   : {path}")
            print(f"        Reason : {reason}")
            print()

    print(f"📝  Log saved to: {log_path}")
    print("=" * 60)

    sys.stdout = tee.terminal
    tee.close()


if __name__ == "__main__":
    find_and_resolve_duplicates()
