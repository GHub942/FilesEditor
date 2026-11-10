import json
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from common import (
    DEFAULT_EXCLUDED_DIRS,
    clear_terminal,
    collect_files,
    print_progress_bar,
    select_target_directory,
)

# Default category mapping
EXTENSION_PREFIXES = {
    "IMG": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".raw", ".heic"},
    "VID": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "ARC": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "AUD": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "DOC": {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".md"},
}
DEFAULT_PREFIX = "FILE"


def sanitize_filename(name: str, replacement: str = "-") -> str:
    """Replace characters that are invalid on Windows (\\ / : * ? " < > |)."""
    sanitized = re.sub(r'[\\/:*?"<>|]', replacement, name)
    return sanitized.strip()


def get_file_prefix(extension: str, prefix_mapping: dict) -> str:
    ext = extension.lower()
    for prefix, ext_set in prefix_mapping.items():
        if ext in ext_set:
            return prefix
    return DEFAULT_PREFIX


def configure_prefixes_and_separator() -> tuple[str, str, dict]:
    print("\n--- ⚙️ FORMAT & PREFIX CUSTOMIZATION ---")

    print("Global prefix:")
    print("  - Leave EMPTY to use each file's parent folder name (DYNAMIC).")
    print("  - Or enter fixed text to apply to ALL files.")
    custom_global = input("Global prefix [Default: parent folder name] : ").strip()

    if custom_global:
        global_prefix = sanitize_filename(custom_global)
    else:
        global_prefix = "AUTO"

    custom_sep = input("\nSeparator between prefix and category [Default: '__'] : ").strip()
    separator = sanitize_filename(custom_sep) if custom_sep else "__"

    mapping = EXTENSION_PREFIXES.copy()
    change_cat = input("\nEdit the category prefixes (IMG, VID, etc.)? (y/N) : ").strip().lower()

    if change_cat in ("y", "yes"):
        new_mapping = {}
        for old_prefix, extensions in mapping.items():
            user_pref = input(
                f"Prefix for {old_prefix} (extensions {tuple(extensions)[:3]}...) [Default: {old_prefix}] : "
            ).strip().upper()
            chosen_prefix = sanitize_filename(user_pref) if user_pref else old_prefix
            new_mapping[chosen_prefix] = extensions
        mapping = new_mapping

    return global_prefix, separator, mapping


def filter_categories(prefix_mapping: dict) -> set[str]:
    available = list(prefix_mapping.keys()) + [DEFAULT_PREFIX]
    print("\n--- 🎯 CATEGORY FILTER ---")
    print(f"Available categories: {', '.join(available)}")
    choice = input("Which categories to process? (e.g. IMG,VID) [Enter = ALL] : ").strip()

    if not choice:
        return set(available)

    selected = {c.strip().upper() for c in choice.split(",") if c.strip()}
    valid_selected = selected.intersection(set(available))

    if not valid_selected:
        return set(available)

    return valid_selected


def gather_files(target_dir: Path):
    """Ask for recursion/exclusions, then collect the files to process."""
    script_name = Path(__file__).name if "__file__" in globals() else None

    recursive = input("\nInclude files from subfolders? (y/N) : ").strip().lower() in ("y", "yes")
    excluded_dirs = set()

    if recursive:
        print("\n💡 Note: dev/temp folders (.venv, temp, node_modules, .git, etc.) are excluded by default.")
        print("   - Type 'TAKE ALL' to include everything without exclusions.")
        print("   - Or enter additional folders to exclude, separated by commas.")

        excl_input = input("\nSubfolder exclusions (Enter = Default | 'TAKE ALL' = None) : ").strip()

        if excl_input.upper() == "TAKE ALL":
            excluded_dirs = set()
        else:
            excluded_dirs = DEFAULT_EXCLUDED_DIRS.copy()
            if excl_input:
                user_dirs = {d.strip() for d in excl_input.split(",") if d.strip()}
                excluded_dirs.update(user_dirs)

    files, subfolder_count = collect_files(
        target_dir, recursive, excluded_dirs, skip_names={script_name}
    )
    return files, recursive, excluded_dirs, subfolder_count


def handle_backups() -> tuple[Path, dict, list[str]]:
    print("\n--- 💾 BACKUP CONFIGURATION ---")
    print("Available options:")
    print("  1. Full file copy (with subfolders)")
    print("  2. Compressed copy (.ZIP) (with subfolders)")
    print("  3. JSON log file (recommended for undo)")
    print("  (Leave empty for NO backup)")

    choices = input("Enter the desired numbers separated by commas (e.g. 1,3) : ").strip().split(",")
    selected = [c.strip() for c in choices if c.strip() in ("1", "2", "3")]

    desktop = Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = desktop / "FilesEditor" / "FilesRenamer" / "Backup" / timestamp

    backup_info = {"dir": None, "has_log": False, "zip_method": zipfile.ZIP_DEFLATED}
    labels = []

    if "1" in selected:
        labels.append("Full copy (tree)")

    if "2" in selected:
        print("\n⚙️ ZIP compression level:")
        print("  1. Stored (no compression)  | ~1-2 sec / GB  (max speed)")
        print("  2. Standard (Deflate)       | ~10-15 sec / GB (balanced) [DEFAULT]")
        print("  3. Maximum (LZMA)           | ~1-2 min / GB   (slow but smaller files)")

        comp_choice = input("Your choice (1/2/3) [Enter=2] : ").strip()
        if comp_choice == "1":
            backup_info["zip_method"] = zipfile.ZIP_STORED
            labels.append("ZIP archive (no compression)")
        elif comp_choice == "3":
            backup_info["zip_method"] = zipfile.ZIP_LZMA
            labels.append("ZIP archive (maximum compression)")
        else:
            backup_info["zip_method"] = zipfile.ZIP_DEFLATED
            labels.append("ZIP archive (standard compression)")

    if "3" in selected:
        labels.append("JSON log (undo_renamer)")
        backup_info["has_log"] = True

    if selected:
        backup_info["dir"] = backup_dir

    return backup_dir, backup_info, labels


def execute_backup_files(backup_dir: Path, selected_labels: list[str], files: list[Path], target_dir: Path, backup_info: dict):
    """Physically create the requested backups with a progress bar."""
    if not backup_dir:
        return

    backup_dir.mkdir(parents=True, exist_ok=True)
    total_files = len(files)
    target_root_name = target_dir.name

    # 1. Full copy
    if any("Full copy" in label for label in selected_labels):
        orig_dir = backup_dir / "Originals"
        for index, path in enumerate(files, start=1):
            rel_path = path.relative_to(target_dir)
            dest = orig_dir / target_root_name / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            print_progress_bar(index, total_files, path.name, step_name="Folder copy")

    # 2. ZIP archive
    if any("ZIP archive" in label for label in selected_labels):
        zip_path = backup_dir / f"{target_root_name}_backup.zip"
        zip_method = backup_info.get("zip_method", zipfile.ZIP_DEFLATED)

        with zipfile.ZipFile(zip_path, "w", zip_method) as zip_file:
            for index, path in enumerate(files, start=1):
                rel_path = path.relative_to(target_dir)
                arcname = Path(target_root_name) / rel_path
                zip_file.write(path, arcname=str(arcname))
                print_progress_bar(index, total_files, path.name, step_name="ZIP creation")


def main():
    while True:
        clear_terminal()
        print("=" * 60)
        print("           AUTOMATIC FILE RENAMER           ")
        print("=" * 60)

        # 1. Configuration
        target_dir = select_target_directory()
        global_prefix_setting, separator, prefix_mapping = configure_prefixes_and_separator()
        allowed_categories = filter_categories(prefix_mapping)
        all_files, recursive, excluded_dirs, subfolder_count = gather_files(target_dir)

        files_to_process = [
            path for path in all_files
            if get_file_prefix(path.suffix, prefix_mapping) in allowed_categories
        ]

        if not files_to_process:
            print("\n⚠️ No files to process. Press Enter to restart...")
            input()
            continue

        digits_input = input("\nMinimum digits for numbering (e.g. 3 -> 001) [Default: 1] : ").strip()
        padding = int(digits_input) if digits_input.isdigit() else 1

        backup_dir, backup_info, backup_labels = handle_backups()

        # 2. Summary & validation
        clear_terminal()
        print("=" * 60)
        print("          📋 CONFIGURATION SUMMARY          ")
        print("=" * 60)
        print(f"📁 Target folder      : {target_dir}")
        print(f"📂 Subfolder mode     : {'Yes (' + str(subfolder_count) + ' subfolder(s) found)' if recursive else 'No'}")
        if recursive and excluded_dirs:
            print(f"🛡️  Excluded folders   : {', '.join(sorted(excluded_dirs))}")
        print(f"🏷️  Global prefix      : {'[DYNAMIC per folder]' if global_prefix_setting == 'AUTO' else global_prefix_setting}")
        print(f"🔗 Separator          : '{separator}'")
        print(f"🎯 Included categories: {', '.join(sorted(allowed_categories))}")
        print(f"🔢 Number padding     : {padding} (e.g. {'1'.zfill(padding)})")
        print(f"📊 Files to process   : {len(files_to_process)} / {len(all_files)} found")
        print(f"💾 Backup enabled     : {', '.join(backup_labels) if backup_labels else 'None'}")
        if backup_dir:
            print(f"📂 Backup location    : {backup_dir}")
        print("=" * 60)

        confirm = input("\nRun the process with these settings? (Y/n) : ").strip().lower()
        if confirm in ("", "y", "yes"):
            break
        print("\n🔄 Cancelled... Reloading settings.")
        time.sleep(1)

    # 3. Execution
    clear_terminal()
    print("=" * 60)
    print("              ⏳ RUNNING PROCESS...              ")
    print("=" * 60 + "\n")

    # Phase A: Backup
    if backup_dir and backup_labels:
        execute_backup_files(backup_dir, backup_labels, files_to_process, target_dir, backup_info)
        print("✅ Backup phase complete.\n")

    # Grouping & planning
    categorized_by_folder = {}
    for path in files_to_process:
        folder_path = path.parent
        category_prefix = get_file_prefix(path.suffix, prefix_mapping)
        categorized_by_folder.setdefault((folder_path, category_prefix), []).append(path)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "target_directory": str(target_dir),
        "separator": separator,
        "renamed_files": [],
    }

    rename_plan = []
    for (folder_path, category_prefix), file_list in categorized_by_folder.items():
        file_list.sort(key=lambda path: path.stat().st_size)
        current_prefix = sanitize_filename(folder_path.name) if global_prefix_setting == "AUTO" else global_prefix_setting

        for index, old_path in enumerate(file_list, start=1):
            index_str = str(index).zfill(padding)
            ext = old_path.suffix.lower()
            final_name = f"{current_prefix}{separator}{category_prefix}_{index_str}{ext}"
            final_path = old_path.parent / final_name
            temp_name = f"__tmp_{uuid.uuid4().hex[:8]}__{ext}"
            temp_path = old_path.parent / temp_name

            rename_plan.append((old_path, temp_path, final_path, old_path.name, final_name))

    total_files = len(rename_plan)
    errors = []

    # Phase B: Temporary rename
    for index, (old_path, temp_path, final_path, orig_name, final_name) in enumerate(rename_plan, start=1):
        try:
            old_path.rename(temp_path)
            print_progress_bar(index, total_files, orig_name, step_name="Pass 1/2 (Temp)")
        except Exception as error:
            errors.append(f"Pass 1 error [{orig_name}]: {error}")

    # Phase C: Final rename
    for index, (old_path, temp_path, final_path, orig_name, final_name) in enumerate(rename_plan, start=1):
        try:
            temp_path.rename(final_path)
            log_data["renamed_files"].append({
                "original_path": str(old_path),
                "new_path": str(final_path),
                "original_name": orig_name,
                "new_name": final_name,
            })
            print_progress_bar(index, total_files, final_name, step_name="Pass 2/2 (Final)")
        except Exception as error:
            errors.append(f"Pass 2 error [{temp_path.name} -> {final_name}]: {error}")

    # Save the log
    if backup_info["has_log"] and backup_info["dir"]:
        log_file = backup_info["dir"] / "rename_log.json"
        with open(log_file, "w", encoding="utf-8") as log_file_handle:
            json.dump(log_data, log_file_handle, ensure_ascii=False, indent=4)

    # 4. Final summary
    clear_terminal()
    print("=" * 60)
    print("           🎉 OPERATION COMPLETED SUCCESSFULLY !          ")
    print("=" * 60)

    print("\n--- ⚙️ Applied Configuration Reminder ---")
    print(f"📁 Target folder      : {target_dir}")
    print(f"🏷️  Prefix used        : {'DYNAMIC (folder name)' if global_prefix_setting == 'AUTO' else global_prefix_setting}")
    print(f"🔗 Separator          : '{separator}'")
    print(f"🔢 Numbering          : padded to {padding} digit(s)")

    print("\n--- 📊 Files & Folders Summary ---")
    print(f"📂 Subfolders scanned    : {subfolder_count}")
    print(f"📄 Total files found     : {len(all_files)}")
    print(f"✅ Files renamed         : {len(log_data['renamed_files'])} / {total_files}")

    if errors:
        print(f"\n❌ ERRORS DETECTED ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✨ No errors detected during the process.")

    if backup_dir and backup_labels:
        print("\n--- 💾 Backup & Rollback Information ---")
        print(f"📍 Backup path         : {backup_dir}")
        print(f"📦 Backed-up items     : {', '.join(backup_labels)}")
        if backup_info["has_log"]:
            print("\n🔄 HOW TO UNDO THIS ACTION (ROLLBACK):")
            print("  1. Run the 'undo_renamer.py' script")
            print("  2. Provide the following log file path:")
            print(f"     '{backup_dir / 'rename_log.json'}'")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
