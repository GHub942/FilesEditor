import json
from pathlib import Path

from common import print_progress_bar


def main():
    print("=" * 65)
    print("       🔄 UNDO EXTEDITOR - EXTENSION RESTORE       ")
    print("=" * 65 + "\n")

    log_input = input("Enter the full path of the 'exteditor_log.json' file: ").strip().strip('"\'')
    log_path = Path(log_input)

    if not log_path.is_file():
        print("\n❌ Log file not found. Make sure you entered the correct path.")
        return

    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            log_data = json.load(log_file)
    except Exception as error:
        print(f"\n❌ Error reading the log file: {error}")
        return

    entries = log_data.get("renamed_files", [])
    total = len(entries)

    if total == 0:
        print("\n⚠️ No modifications recorded in this log file.")
        return

    print(f"\n🔍 {total} extension(s) to restore...\n")
    restored = 0
    errors = 0

    for index, entry in enumerate(entries, start=1):
        current_file = Path(entry["new_path"])
        original_file = Path(entry["original_path"])

        if current_file.exists():
            try:
                current_file.rename(original_file)
                restored += 1
                print_progress_bar(index, total, original_file.name, step_name="Restore")
            except Exception:
                errors += 1
                print_progress_bar(index, total, f"Error: {current_file.name}", step_name="Restore")
        else:
            errors += 1
            print_progress_bar(index, total, f"Not found: {current_file.name}", step_name="Restore")

    print("\n" + "=" * 65)
    print("🎉 Restore completed successfully!")
    print(f"📊 Files restored: {restored} / {total}")
    if errors > 0:
        print(f"⚠️ Errors encountered: {errors}")
    print("=" * 65)


if __name__ == "__main__":
    main()
