import json
from pathlib import Path

from common import print_progress_bar


def main():
    print("=" * 60)
    print("         RESTORING ORIGINAL NAMES (UNDO)         ")
    print("=" * 60 + "\n")

    log_input = input("Enter the full path of the 'rename_log.json' file: ").strip().strip('"\'')
    log_path = Path(log_input)

    if not log_path.is_file():
        print("❌ Log file not found.")
        return

    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            log_data = json.load(log_file)
    except Exception as error:
        print(f"❌ Error reading the log file: {error}")
        return

    entries = log_data.get("renamed_files", [])
    if not entries:
        print("⚠️ No entries found in this log.")
        return

    total = len(entries)
    print(f"\n🔍 {total} file(s) to restore.\n")
    print_progress_bar(0, total, "Initializing...")

    restored = 0
    errors = 0

    for index, entry in enumerate(entries, start=1):
        current_file = Path(entry["new_path"])
        original_file = Path(entry["original_path"])

        if current_file.exists():
            current_file.rename(original_file)
            restored += 1
            print_progress_bar(index, total, original_file.name, step_name="Restore")
        else:
            errors += 1
            print_progress_bar(index, total, f"Not found: {current_file.name}", step_name="Restore")

    print("\n" + "=" * 60)
    print(f"✅ Restore complete! ({restored} succeeded, {errors} errors)")
    print("=" * 60)


if __name__ == "__main__":
    main()
