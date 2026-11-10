import json
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

# File categories with their recognized extensions + default target extension
DEFAULT_MEDIA_MAPPING = {
    "IMG": {
        "label": "Images",
        "target_ext": ".png",
        "exts": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".raw", ".heic"},
    },
    "VID": {
        "label": "Videos",
        "target_ext": ".mp4",
        "exts": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    },
    "AUD": {
        "label": "Audio",
        "target_ext": ".mp3",
        "exts": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    },
    "DOC": {
        "label": "Documents",
        "target_ext": ".pdf",
        "exts": {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".md"},
    },
    "ARC": {
        "label": "Archives",
        "target_ext": ".zip",
        "exts": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    },
}


def configure_target_extensions() -> dict:
    """Let the user choose which extension to assign to each category."""
    print("\n--- 🎯 TARGET EXTENSION SELECTION ---")
    print("Choose the extension to apply for each file type.")
    print("(Press Enter to keep the default value)\n")

    custom_mapping = {}
    for cat_key, info in DEFAULT_MEDIA_MAPPING.items():
        default_ext = info["target_ext"]
        user_input = input(f"Ext. for {info['label']:<10} (e.g. .png, .jpg) [Default: {default_ext}] : ").strip().lower()

        if user_input:
            if not user_input.startswith("."):
                user_input = f".{user_input}"
            target = user_input
        else:
            target = default_ext

        custom_mapping[cat_key] = {
            "label": info["label"],
            "target_ext": target,
            "exts": info["exts"],
        }

    return custom_mapping


def get_target_extension(current_ext: str, media_mapping: dict) -> str:
    ext = current_ext.lower()
    for data in media_mapping.values():
        if ext in data["exts"]:
            return data["target_ext"]
    return ext  # Keep the original extension if unrecognized


def gather_files(target_dir: Path):
    """Ask for recursion/exclusions, then collect the files to process."""
    script_name = Path(__file__).name if "__file__" in globals() else None

    recursive = input("\nInclude files from subfolders? (y/N) : ").strip().lower() in ("y", "yes")
    excluded_dirs = set()

    if recursive:
        print("\n💡 Note: dev/temp folders (.venv, node_modules, etc.) are excluded by default.")
        print("   - Type 'TAKE ALL' to include everything.")
        print("   - Or enter folders to exclude, separated by commas.")

        excl_input = input("\nSubfolder exclusions (Enter = Default | 'TAKE ALL' = None) : ").strip()

        if excl_input.upper() == "TAKE ALL":
            excluded_dirs = set()
        else:
            excluded_dirs = DEFAULT_EXCLUDED_DIRS.copy()
            if excl_input:
                user_dirs = {d.strip() for d in excl_input.split(",") if d.strip()}
                excluded_dirs.update(user_dirs)

    files, subfolder_count = collect_files(
        target_dir,
        recursive,
        excluded_dirs,
        skip_names={script_name},
        skip_prefixes=("undo_",),
    )
    return files, recursive, excluded_dirs, subfolder_count


def handle_backups() -> tuple[Path, dict, list[str]]:
    print("\n--- 💾 BACKUP CONFIGURATION ---")
    print("Available options:")
    print("  1. Full file copy (complete reconstruction)")
    print("  2. Archive (.ZIP)")
    print("  3. JSON restore log (recommended for undo_exteditor.py)")

    choices = input("Choice (e.g. 1,3) [Enter = JSON log only] : ").strip().split(",")
    selected = [c.strip() for c in choices if c.strip() in ("1", "2", "3")]
    if not choices or choices == [""]:
        selected = ["3"]

    desktop = Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Exact path: Desktop\FilesEditor\Exteditor\Backup\TIME
    backup_dir = desktop / "FilesEditor" / "Exteditor" / "Backup" / timestamp

    backup_info = {"dir": None, "has_log": False, "zip_method": zipfile.ZIP_DEFLATED}
    labels = []

    if "1" in selected:
        labels.append("Full copy")
    if "2" in selected:
        backup_info["zip_method"] = zipfile.ZIP_DEFLATED
        labels.append("ZIP archive")
    if "3" in selected:
        labels.append("JSON log (undo_exteditor)")
        backup_info["has_log"] = True

    if selected:
        backup_info["dir"] = backup_dir

    return backup_dir, backup_info, labels


def execute_backup_files(backup_dir: Path, selected_labels: list[str], files: list[Path], target_dir: Path, backup_info: dict):
    if not backup_dir:
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    total_files = len(files)
    target_root_name = target_dir.name

    if any("Full copy" in label for label in selected_labels):
        orig_dir = backup_dir / "Full_Copy"
        for index, path in enumerate(files, start=1):
            rel_path = path.relative_to(target_dir)
            dest = orig_dir / target_root_name / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            print_progress_bar(index, total_files, path.name, step_name="Folder copy")

    if any("ZIP archive" in label for label in selected_labels):
        zip_path = backup_dir / f"{target_root_name}_backup.zip"
        with zipfile.ZipFile(zip_path, "w", backup_info.get("zip_method", zipfile.ZIP_DEFLATED)) as zip_file:
            for index, path in enumerate(files, start=1):
                rel_path = path.relative_to(target_dir)
                arcname = Path(target_root_name) / rel_path
                zip_file.write(path, arcname=str(arcname))
                print_progress_bar(index, total_files, path.name, step_name="ZIP creation")


def main():
    while True:
        clear_terminal()
        print("=" * 65)
        print("         🖥️ EXTEDITOR - EXTENSION EDITOR")
        print("=" * 65)

        target_dir = select_target_directory()
        media_mapping = configure_target_extensions()
        all_files, recursive, excluded_dirs, subfolder_count = gather_files(target_dir)

        if not all_files:
            print("\n⚠️ No files to process. Press Enter to restart...")
            input()
            continue

        backup_dir, backup_info, backup_labels = handle_backups()

        clear_terminal()
        print("=" * 65)
        print("          📋 CONFIGURATION SUMMARY          ")
        print("=" * 65)
        print(f"📁 Target folder      : {target_dir}")
        print(f"📂 Subfolders         : {'Yes (' + str(subfolder_count) + ' scanned)' if recursive else 'No'}")
        if recursive:
            print(f"🛡️  Exclusions         : {', '.join(sorted(excluded_dirs)) if excluded_dirs else 'None (TAKE ALL)'}")

        print("\n🎯 Chosen extensions:")
        for info in media_mapping.values():
            print(f"   - {info['label']:<10} ➔ {info['target_ext']}")

        print(f"\n📊 Files detected     : {len(all_files)}")
        print(f"💾 Backups            : {', '.join(backup_labels) if backup_labels else 'None'}")
        if backup_dir:
            print(f"📂 Backup path        : {backup_dir}")
        print("=" * 65)

        confirm = input("\nStart the extension change? (Y/n) : ").strip().lower()
        if confirm in ("", "y", "yes"):
            break
        print("\n🔄 Resetting...")
        time.sleep(1)

    clear_terminal()
    print("=" * 65)
    print("              ⏳ PROCESSING...              ")
    print("=" * 65 + "\n")

    if backup_dir and backup_labels:
        execute_backup_files(backup_dir, backup_labels, all_files, target_dir, backup_info)
        print("✅ Backup completed.\n")

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "target_directory": str(target_dir),
        "renamed_files": [],
    }

    errors = []
    total_files = len(all_files)

    for index, old_path in enumerate(all_files, start=1):
        try:
            target_ext = get_target_extension(old_path.suffix, media_mapping)

            # Skip files whose extension is already correct
            if old_path.suffix.lower() == target_ext.lower():
                print_progress_bar(index, total_files, old_path.name, step_name="Already OK")
                continue

            # Keep the exact original name and apply the chosen target extension
            new_path = old_path.with_suffix(target_ext)

            # Handle collisions if a file with this new extension already exists
            if new_path.exists() and new_path != old_path:
                new_path = old_path.with_name(f"{old_path.stem}_{uuid.uuid4().hex[:4]}{target_ext}")

            old_path.rename(new_path)

            log_data["renamed_files"].append({
                "original_path": str(old_path),
                "new_path": str(new_path),
                "original_name": old_path.name,
                "new_name": new_path.name,
            })
            print_progress_bar(index, total_files, new_path.name, step_name="Extension changed")

        except Exception as error:
            errors.append(f"Error on [{old_path.name}]: {error}")

    if backup_info["has_log"] and backup_info["dir"]:
        log_file = backup_info["dir"] / "exteditor_log.json"
        with open(log_file, "w", encoding="utf-8") as log_file_handle:
            json.dump(log_data, log_file_handle, ensure_ascii=False, indent=4)

    clear_terminal()
    print("=" * 65)
    print("           🎉 OPERATION COMPLETED SUCCESSFULLY !          ")
    print("=" * 65)

    print("\n--- 📊 Statistics ---")
    print(f"📂 Subfolders scanned   : {subfolder_count}")
    print(f"📄 Files scanned        : {total_files}")
    print(f"✅ Extensions changed   : {len(log_data['renamed_files'])}")

    print("\n--- 🚨 Error Report ---")
    if errors:
        for error in errors:
            print(f"  - {error}")
    else:
        print("✨ No errors")

    if backup_dir and backup_info["has_log"]:
        print("\n--- 🔄 Rollback Procedure ---")
        print("  1. Run: 'python undo_exteditor.py'")
        print(f"  2. Use the log file: {backup_dir / 'exteditor_log.json'}")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
