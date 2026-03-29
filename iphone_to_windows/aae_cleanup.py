import os
from datetime import datetime

# ANSI colors
GREEN = "\033[92m"
RESET = "\033[0m"

# Base directory
base_dir = os.path.dirname(os.path.abspath(__file__))

print("\nScanning folders in:")
print(base_dir, "\n")

# Get folders
folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]

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
    print(f"{f['name']} --> {f['count']} files")
    total += f["count"]

print(f"TOTAL .aae files to delete: {total}\n")

# Confirm
confirm = input("Type YES to confirm deletion: ")
if confirm != "YES":
    print("Operation cancelled.")
    exit()

# Persistent log file
log_file = os.path.join(base_dir, "AAE_Delete_Log.txt")

# Append mode
with open(log_file, "a", encoding="utf-8") as log:

    # Session header
    log.write("\n" + "="*60 + "\n")
    log.write(f"Run at: {datetime.now()}\n")
    log.write(f"Base Directory: {base_dir}\n")
    log.write("="*60 + "\n")

    # Delete files
    for f in selected:
        if f["count"] == 0:
            print(f"Skipping {f['name']} (no .aae files)")
            log.write(f"{datetime.now()} | {f['name']} | No files to delete\n")
            continue

        for root, _, files in os.walk(f["path"]):
            for file in files:
                if file.lower().endswith(".aae"):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        log.write(f"{datetime.now()} | DELETED | {file_path}\n")
                    except Exception as e:
                        log.write(f"{datetime.now()} | ERROR | {file_path} | {e}\n")

        print(f"Deleted .aae files from {f['name']}")
        log.write(f"{datetime.now()} | COMPLETED | {f['name']}\n")

print("\nDone.")
print(f"Log updated at: {log_file}")

input("\nPress Enter to exit...")