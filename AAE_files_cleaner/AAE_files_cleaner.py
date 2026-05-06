import os
import shutil
from datetime import datetime

# ANSI colors
GREEN = "\033[92m"
RESET = "\033[0m"

# Base directory
base_dir = os.path.dirname(os.path.abspath(__file__))

# Destination folder for all moved .aae files
aae_folder = os.path.join(base_dir, "AAE_files")

print("\nScanning folders in:")
print(base_dir, "\n")

# Get folders (exclude the AAE_files destination folder itself)
folders = [
    f for f in os.listdir(base_dir)
    if os.path.isdir(os.path.join(base_dir, f)) and f != "AAE_files"
]

if not folders:
    print("No folders found.")
    input("Press Enter to exit...")
    exit()

folder_data = []

# Count .aae files
for i, folder in enumerate(folders, start=1):
    folder_path = os.path.join(base_dir, folder)
    count = 0

    for root, _, files in os.walk(folder_path):
        count += sum(1 for file in files if file.lower().endswith(".aae"))

    folder_data.append({
        "index": i,
        "name": folder,
        "path": folder_path,
        "count": count
    })

    if count == 0:
        print(f"[{i}] {GREEN}{folder} --> {count} .aae files{RESET}")
    else:
        print(f"[{i}] {folder} --> {count} .aae files")

print("\n[*] ALL folders\n")

# Input
choice = input("Enter folder number(s) (e.g., 1,3,5) or *: ").strip()

selected = []

if choice == "*":
    selected = folder_data
else:
    try:
        indices = [int(x.strip()) for x in choice.split(",")]
        for idx in indices:
            match = next((f for f in folder_data if f["index"] == idx), None)
            if match:
                selected.append(match)
            else:
                print(f"Invalid selection: {idx}")
                exit()
    except ValueError:
        print("Invalid input format.")
        exit()

# Remove duplicates
selected = list({f["index"]: f for f in selected}.values())

# Summary
print("\nSummary:")
total = 0
for f in selected:
    print(f"  {f['name']} --> {f['count']} files")
    total += f["count"]

print(f"\n  TOTAL .aae files to move: {total}\n")

# Confirm
confirm = input("Type YES to confirm move: ")
if confirm != "YES":
    print("Operation cancelled.")
    exit()

# Create the AAE_files destination folder if it doesn't exist
os.makedirs(aae_folder, exist_ok=True)

# Persistent log file
log_file = os.path.join(base_dir, "log-AAE_files_cleaner.txt")

# Track results for summary
total_moved = 0
total_errors = 0
moved_list = []

# Append mode
with open(log_file, "a", encoding="utf-8") as log:

    # Session header
    log.write("\n" + "=" * 60 + "\n")
    log.write(f"Run at: {datetime.now()}\n")
    log.write(f"Base Directory: {base_dir}\n")
    log.write(f"Destination:    {aae_folder}\n")
    log.write("=" * 60 + "\n")

    # Move files
    for f in selected:
        if f["count"] == 0:
            print(f"  Skipping {f['name']} (no .aae files)")
            log.write(f"{datetime.now()} | {f['name']} | No files to move\n")
            continue

        for root, _, files in os.walk(f["path"]):
            for file in files:
                if file.lower().endswith(".aae"):
                    src_path = os.path.join(root, file)

                    # Handle name collisions in the destination folder
                    dest_name = file
                    dest_path = os.path.join(aae_folder, dest_name)
                    counter = 1
                    base_name, ext = os.path.splitext(file)
                    while os.path.exists(dest_path):
                        dest_name = f"{base_name}__{counter}{ext}"
                        dest_path = os.path.join(aae_folder, dest_name)
                        counter += 1

                    try:
                        shutil.move(src_path, dest_path)
                        log.write(f"{datetime.now()} | MOVED | {src_path} --> {dest_path}\n")
                        moved_list.append((src_path, dest_path))
                        total_moved += 1
                    except Exception as e:
                        log.write(f"{datetime.now()} | ERROR | {src_path} | {e}\n")
                        total_errors += 1

        print(f"  Moved .aae files from: {f['name']}")
        log.write(f"{datetime.now()} | COMPLETED | {f['name']}\n")

    # Write summary to log
    log.write("\n" + "-" * 60 + "\n")
    log.write(f"SUMMARY\n")
    log.write(f"  Total moved : {total_moved}\n")
    log.write(f"  Total errors: {total_errors}\n")
    if moved_list:
        log.write(f"\n  Files moved:\n")
        for i, (src, dst) in enumerate(moved_list, 1):
            log.write(f"  {i:>4}. {os.path.basename(src)}\n")
            log.write(f"        From : {src}\n")
            log.write(f"        To   : {dst}\n")
    log.write("-" * 60 + "\n")

# Print summary to screen
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if moved_list:
    print(f"\n📦  {total_moved} file(s) moved to: {aae_folder}\n")
    for i, (src, dst) in enumerate(moved_list, 1):
        print(f"  {i:>4}.  {os.path.basename(src)}")
        print(f"          From : {src}")
        print(f"          To   : {dst}")
        print()
else:
    print("\n  No files were moved.")

if total_errors:
    print(f"\n  ⚠️  {total_errors} error(s) occurred — check log for details.")

print(f"\n📝  Log updated at: {log_file}")
print("=" * 60)

input("\nPress Enter to exit...")
