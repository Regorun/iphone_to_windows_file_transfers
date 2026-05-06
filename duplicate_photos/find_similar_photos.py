#!/usr/bin/env python3
"""

Similar Photo Finder
--------------------
Scans the folder it lives in (and all subfolders) for visually similar photos.
Groups them into:
  - NEAR-IDENTICAL  : burst shots, resized/cropped copies  (threshold <= 6)
  - LOOSELY SIMILAR : same scene, similar composition      (threshold 7-20)

For each group the largest file (highest resolution) is kept in place.
All others are moved to 'similar_photos/' with two subfolders:
  similar_photos/near_identical/
  similar_photos/loosely_similar/

Requires:
  pip install Pillow imagehash
"""

import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations

# ---------------------------------------------------------------------------
# Dependency check — give a clear error if packages are missing
# ---------------------------------------------------------------------------
try:
    from PIL import Image
    import imagehash
except ImportError:
    print("=" * 60)
    print("ERROR: Required packages are not installed.")
    print("")
    print("Please run the following command and try again:")
    print("")
    print("  pip install Pillow imagehash")
    print("=" * 60)
    input("\nPress Enter to exit...")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tiff", ".gif"}

# Hamming distance thresholds (lower = more similar)
NEAR_IDENTICAL_THRESHOLD = 6   # burst shots, resized, cropped
LOOSELY_SIMILAR_THRESHOLD = 20  # same scene, similar composition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_exe_dir():
    """Returns the folder the .exe or .py is running from."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def folder_depth(path):
    return len(os.path.abspath(path).split(os.sep))


def compute_phash(filepath):
    """
    Computes a perceptual hash (pHash) for an image.
    Returns None if the file cannot be opened (corrupt, unsupported, etc.)
    HEIC files require pillow-heif — falls back gracefully if not installed.
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".heic":
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                return None  # silently skip if pillow-heif not installed

        with Image.open(filepath) as img:
            img = img.convert("RGB")
            return imagehash.phash(img)
    except Exception:
        return None


def pick_keeper(paths):
    """
    Given a list of paths in a similarity group, returns the one to KEEP.
    Rule: largest file size wins (highest resolution proxy).
    Tiebreaker: shallowest folder depth.
    Second tiebreaker: alphabetically earliest parent folder.
    """
    def sort_key(p):
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0
        depth = folder_depth(p)
        parent = os.path.dirname(os.path.abspath(p)).lower()
        return (-size, depth, parent)

    return sorted(paths, key=sort_key)[0]


def move_file(src, dest_dir):
    """
    Moves src into dest_dir, handling filename collisions.
    Returns (dest_path, success).
    """
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(src)
    dest_path = os.path.join(dest_dir, filename)

    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir, f"{base}__{counter}{ext}")
        counter += 1

    try:
        shutil.move(src, dest_path)
        return dest_path, True
    except OSError as e:
        print(f"  ❌ Failed to move {src}: {e}")
        return None, False


def union_find_groups(pairs):
    """
    Given a list of (path_a, path_b) similar pairs, groups them into
    clusters using Union-Find so transitive similarities are merged.
    e.g. if A~B and B~C then {A, B, C} become one group.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        parent[find(x)] = find(y)

    for a, b in pairs:
        union(a, b)

    groups = defaultdict(list)
    for node in parent:
        groups[find(node)].append(node)

    return [g for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def find_similar_photos():
    script_dir = get_exe_dir()
    output_dir       = os.path.join(script_dir, "similar_photos")
    near_dir         = os.path.join(output_dir, "near_identical")
    loose_dir        = os.path.join(output_dir, "loosely_similar")
    log_path         = os.path.join(script_dir, "similar_photos_log.txt")

    print("\n" + "=" * 60)
    print("  Similar Photo Finder")
    print("=" * 60)
    print(f"  Scanning: {script_dir}\n")

    # --- Step 1: Collect all supported image files ---
    all_photos = []
    skipped_dirs = []

    for dirpath, dirnames, filenames in os.walk(script_dir):
        # Skip the output folder
        dirnames[:] = [
            d for d in dirnames
            if os.path.join(dirpath, d) != output_dir
        ]

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, filename)

            # Skip the script / exe itself (shouldn't match but just in case)
            if getattr(sys, "frozen", False):
                if os.path.abspath(full_path) == os.path.abspath(sys.executable):
                    continue
            else:
                if os.path.abspath(full_path) == os.path.abspath(__file__):
                    continue

            all_photos.append(full_path)

    total = len(all_photos)
    if total == 0:
        print("  No supported photo files found.")
        input("\nPress Enter to exit...")
        return

    print(f"  Found {total} photo(s). Computing perceptual hashes...\n")

    # --- Step 2: Hash all photos ---
    hashes = {}
    failed = []

    for i, path in enumerate(all_photos, 1):
        print(f"  [{i:>5}/{total}] Hashing: {os.path.basename(path)}", end="\r")
        h = compute_phash(path)
        if h is not None:
            hashes[path] = h
        else:
            failed.append(path)

    print(f"\n\n  ✅ Hashed {len(hashes)} photo(s). "
          f"{len(failed)} skipped (corrupt or unsupported).\n")

    # --- Step 3: Compare all pairs ---
    print("  Comparing all pairs for similarity...\n")

    paths = list(hashes.keys())
    near_pairs  = []
    loose_pairs = []

    total_pairs = len(paths) * (len(paths) - 1) // 2
    checked = 0

    for path_a, path_b in combinations(paths, 2):
        checked += 1
        if checked % 500 == 0 or checked == total_pairs:
            print(f"  Compared {checked:,} / {total_pairs:,} pairs...", end="\r")

        distance = hashes[path_a] - hashes[path_b]

        if distance <= NEAR_IDENTICAL_THRESHOLD:
            near_pairs.append((path_a, path_b))
        elif distance <= LOOSELY_SIMILAR_THRESHOLD:
            loose_pairs.append((path_a, path_b))

    print(f"\n\n  Found {len(near_pairs)} near-identical pair(s).")
    print(f"  Found {len(loose_pairs)} loosely similar pair(s).\n")

    # --- Step 4: Cluster pairs into groups ---
    near_groups  = union_find_groups(near_pairs)
    loose_groups = union_find_groups(loose_pairs)

    if not near_groups and not loose_groups:
        print("  ✅ No similar photos found.")
        input("\nPress Enter to exit...")
        return

    # --- Step 5: Print summary ---
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    total_to_move = 0

    if near_groups:
        print(f"\n  🔴 NEAR-IDENTICAL GROUPS ({len(near_groups)} group(s))\n")
        for i, group in enumerate(near_groups, 1):
            keeper = pick_keeper(group)
            to_move = [p for p in group if p != keeper]
            total_to_move += len(to_move)
            print(f"  Group {i} — {len(group)} photos:")
            for p in group:
                tag = "KEEP  ✅" if p == keeper else "MOVE  📦"
                try:
                    size = f"{os.path.getsize(p):,} bytes"
                except OSError:
                    size = "unknown"
                print(f"    [{tag}]  {os.path.basename(p)}")
                print(f"             {p}  ({size})")
            print()

    if loose_groups:
        print(f"\n  🟡 LOOSELY SIMILAR GROUPS ({len(loose_groups)} group(s))\n")
        for i, group in enumerate(loose_groups, 1):
            keeper = pick_keeper(group)
            to_move = [p for p in group if p != keeper]
            total_to_move += len(to_move)
            print(f"  Group {i} — {len(group)} photos:")
            for p in group:
                tag = "KEEP  ✅" if p == keeper else "MOVE  📦"
                try:
                    size = f"{os.path.getsize(p):,} bytes"
                except OSError:
                    size = "unknown"
                print(f"    [{tag}]  {os.path.basename(p)}")
                print(f"             {p}  ({size})")
            print()

    print("-" * 60)
    print(f"  Total files to move : {total_to_move}")
    print(f"  Destination (near)  : {near_dir}")
    print(f"  Destination (loose) : {loose_dir}")
    print("-" * 60)

    # --- Step 6: Confirm ---
    print()
    confirm = input("  Type YES to move the files, or anything else to cancel: ").strip()
    if confirm != "YES":
        print("\n  Operation cancelled. No files were moved.")
        input("\nPress Enter to exit...")
        return

    # --- Step 7: Move files and log ---
    moved_files  = []
    error_files  = []

    with open(log_path, "a", encoding="utf-8") as log:
        log.write("\n" + "=" * 60 + "\n")
        log.write(f"RUN — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Scanning: {script_dir}\n")
        log.write("=" * 60 + "\n")

        for label, groups, dest_dir in [
            ("NEAR-IDENTICAL",  near_groups,  near_dir),
            ("LOOSELY-SIMILAR", loose_groups, loose_dir),
        ]:
            for i, group in enumerate(groups, 1):
                keeper = pick_keeper(group)
                log.write(f"\n[{label}] Group {i}\n")
                log.write(f"  KEEP: {keeper}\n")

                for p in group:
                    if p == keeper:
                        continue
                    dest_path, success = move_file(p, dest_dir)
                    if success:
                        moved_files.append((p, dest_path, label))
                        log.write(f"  MOVED: {p}\n")
                        log.write(f"      → {dest_path}\n")
                    else:
                        error_files.append(p)
                        log.write(f"  ERROR: {p}\n")

        # Summary in log
        log.write("\n" + "-" * 60 + "\n")
        log.write(f"SUMMARY\n")
        log.write(f"  Total moved : {len(moved_files)}\n")
        log.write(f"  Total errors: {len(error_files)}\n")
        log.write("-" * 60 + "\n")

    # --- Step 8: Final screen summary ---
    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)

    if moved_files:
        print(f"\n  📦 {len(moved_files)} file(s) moved:\n")
        for i, (src, dst, label) in enumerate(moved_files, 1):
            print(f"  {i:>4}.  [{label}]  {os.path.basename(src)}")
            print(f"          From : {src}")
            print(f"          To   : {dst}")
            print()

    if error_files:
        print(f"\n  ❌ {len(error_files)} file(s) failed to move:")
        for p in error_files:
            print(f"      {p}")

    print(f"\n  📝 Log saved to: {log_path}")
    print("=" * 60)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    find_similar_photos()
