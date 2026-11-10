import json
import os
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_EXCLUDED_DIRS = {
    ".venv", "venv", "env", ".env", "temp", "tmp", ".temp", ".tmp",
    "node_modules", ".git", "__pycache__", ".idea", ".vscode",
}
DEFAULT_EXCLUDED_EXTENSIONS = {".tmp", ".bak"}

CATEGORY_EXTENSIONS = {
    "IMG": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".raw", ".heic"},
    "VID": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "ARC": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "AUD": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "DOC": {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".md"},
}

EXTENSION_TARGETS = {
    "IMG": ".png",
    "VID": ".mp4",
    "AUD": ".mp3",
    "DOC": ".pdf",
    "ARC": ".zip",
}

_EXTENSION_TO_CATEGORY = {
    extension: category
    for category, extensions in CATEGORY_EXTENSIONS.items()
    for extension in extensions
}


class OperationError(ValueError):
    pass


@dataclass
class OperationPreview:
    root: Path
    kind: str
    entries: list[dict]
    log_data: dict
    created_at: float


def _resolve_root(raw_path):
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise OperationError("Enter a folder path.")
    try:
        root = Path(raw_path.strip().strip('"')).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise OperationError(f"Folder could not be opened: {error}") from error
    if not root.is_dir():
        raise OperationError("The selected path is not a folder.")
    return root


def _collect_files(root, recursive, excluded_dirs, excluded_extensions=None):
    excluded_extensions = excluded_extensions or set()
    files = []
    if recursive:
        def raise_walk_error(error):
            raise OperationError(f"Could not scan a folder: {error}") from error

        for current, dirs, names in os.walk(root, followlinks=False, onerror=raise_walk_error):
            dirs[:] = [name for name in dirs if name not in excluded_dirs]
            for name in names:
                path = Path(current) / name
                if not path.is_symlink():
                    if path.suffix.lower() not in excluded_extensions:
                        files.append(path)
    else:
        try:
            files.extend(
                item for item in root.iterdir()
                if item.is_file() and not item.is_symlink() and item.suffix.lower() not in excluded_extensions
            )
        except OSError as error:
            raise OperationError(f"Could not list the selected folder: {error}") from error
    return sorted(files, key=lambda path: (str(path.parent).casefold(), path.name.casefold()))


def _category_for(path):
    return _EXTENSION_TO_CATEGORY.get(path.suffix.lower(), "FILE")


def _sanitize_filename(value, replacement="-"):
    return re.sub(r'[\\/:*?"<>|]', replacement, value).strip().rstrip(". ")


def _format_path(root, path):
    return path.relative_to(root).as_posix()


def _plan_rename(root, files, options):
    prefix_setting = options.get("globalPrefix", "")
    separator = options.get("separator", "__")
    if not isinstance(prefix_setting, str) or not isinstance(separator, str):
        raise OperationError("The prefix and separator must be text.")
    prefix_setting = prefix_setting.strip()
    prefix_setting = _sanitize_filename(prefix_setting) if prefix_setting else "AUTO"
    separator = _sanitize_filename(separator) or "__"
    try:
        padding = int(options.get("padding", 1))
    except (TypeError, ValueError) as error:
        raise OperationError("Number padding must be a whole number.") from error
    if padding < 1 or padding > 12:
        raise OperationError("Number padding must be between 1 and 12.")

    custom_prefixes = options.get("categoryPrefixes", {})
    if not isinstance(custom_prefixes, dict):
        raise OperationError("Category prefixes must be an object.")
    prefixes = {}
    for category in CATEGORY_EXTENSIONS:
        value = custom_prefixes.get(category, category)
        if not isinstance(value, str) or not _sanitize_filename(value):
            raise OperationError(f"Enter a valid prefix for {category}.")
        prefixes[category] = _sanitize_filename(value).upper()
    allowed = options.get("categories", list(CATEGORY_EXTENSIONS) + ["FILE"])
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise OperationError("Choose one or more valid categories.")
    allowed = {item.upper() for item in allowed}
    valid_categories = set(CATEGORY_EXTENSIONS) | {"FILE"}
    if not allowed or not allowed.issubset(valid_categories):
        raise OperationError("Choose one or more valid categories.")

    groups = {}
    for path in files:
        category = _category_for(path)
        if category in allowed:
            groups.setdefault((path.parent, category), []).append(path)

    planned = []
    for (folder, category), group in groups.items():
        group.sort(key=lambda path: (path.stat().st_size, path.name.casefold()))
        folder_prefix = _sanitize_filename(folder.name) if prefix_setting == "AUTO" else prefix_setting
        category_prefix = prefixes.get(category, "FILE")
        for index, old_path in enumerate(group, start=1):
            extension = old_path.suffix.lower()
            name = f"{folder_prefix}{separator}{category_prefix}_{str(index).zfill(padding)}{extension}"
            new_path = old_path.with_name(name)
            if new_path != old_path:
                planned.append({"old": old_path, "new": new_path})
    return planned, {"separator": separator}


def _plan_extensions(files, options):
    custom_targets = options.get("targets", {})
    if not isinstance(custom_targets, dict):
        raise OperationError("Extension targets must be an object.")
    targets = {}
    for category, default in EXTENSION_TARGETS.items():
        value = custom_targets.get(category, default)
        if not isinstance(value, str):
            raise OperationError(f"Enter a valid extension for {category}.")
        extension = value.strip().lower()
        if not extension.startswith("."):
            extension = "." + extension
        if not re.fullmatch(r"\.[a-z0-9][a-z0-9_-]{0,15}", extension):
            raise OperationError(f"Invalid extension for {category}: {value}")
        targets[category] = extension

    planned = []
    reserved = set()
    for old_path in files:
        category = _category_for(old_path)
        target_ext = targets.get(category)
        if target_ext is None or old_path.suffix.lower() == target_ext:
            continue
        new_path = old_path.with_suffix(target_ext)
        suffix = 1
        while new_path.exists() or new_path in reserved:
            new_path = old_path.with_name(f"{old_path.stem}_{suffix}{target_ext}")
            suffix += 1
        reserved.add(new_path)
        planned.append({"old": old_path, "new": new_path})
    return planned, {"targets": targets}


def _plan_undo(root, log_data):
    if not isinstance(log_data, dict) or not isinstance(log_data.get("renamed_files"), list):
        raise OperationError("The selected JSON file is not a valid undo log.")
    recorded_root = log_data.get("target_directory")
    if not isinstance(recorded_root, str):
        raise OperationError("The undo log does not contain a target folder.")
    try:
        expected_root = Path(recorded_root).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise OperationError(f"The folder recorded in the log is unavailable: {error}") from error
    if expected_root != root:
        raise OperationError("The selected folder must match the folder recorded in the undo log.")

    planned = []
    for entry in log_data["renamed_files"]:
        if not isinstance(entry, dict):
            raise OperationError("The undo log contains an invalid entry.")
        old_value, new_value = entry.get("original_path"), entry.get("new_path")
        if not isinstance(old_value, str) or not isinstance(new_value, str):
            raise OperationError("An undo log entry is missing its file paths.")
        old_path, new_path = Path(old_value).resolve(), Path(new_value).resolve()
        try:
            old_path.relative_to(root)
            new_path.relative_to(root)
        except ValueError as error:
            raise OperationError("The undo log contains a path outside the selected folder.") from error
        if old_path.parent != new_path.parent:
            raise OperationError("The undo log contains a file move; only same-folder renames can be restored.")
        planned.append({"old": new_path, "new": old_path})
    return planned, {"timestamp": log_data.get("timestamp")}


def create_preview(kind, options):
    if kind not in {"rename", "extensions", "undo"}:
        raise OperationError("Unknown operation.")
    root = _resolve_root(options.get("folder"))
    if kind == "undo":
        planned, details = _plan_undo(root, options.get("log"))
    else:
        recursive = options.get("recursive", False)
        if not isinstance(recursive, bool):
            raise OperationError("Subfolder scanning must be enabled or disabled.")
        if options.get("takeAll"):
            excluded = set()
            excluded_extensions = set()
        else:
            custom_excluded = options.get("excludedDirs", [])
            if not isinstance(custom_excluded, list) or any(not isinstance(item, str) for item in custom_excluded):
                raise OperationError("Excluded folders must be a list of folder names.")
            custom_directories = {item.strip() for item in custom_excluded if item.strip()}
            excluded = custom_directories if "excludedDirs" in options else DEFAULT_EXCLUDED_DIRS | custom_directories
            custom_extensions = options.get("excludedExtensions", [])
            if not isinstance(custom_extensions, list) or any(not isinstance(item, str) for item in custom_extensions):
                raise OperationError("Excluded extensions must be a list of file extensions.")
            parsed_extensions = {
                item.strip().lower() if item.strip().startswith(".") else f".{item.strip().lower()}"
                for item in custom_extensions if item.strip()
            }
            excluded_extensions = parsed_extensions if "excludedExtensions" in options else DEFAULT_EXCLUDED_EXTENSIONS | parsed_extensions
        files = _collect_files(root, recursive, excluded, excluded_extensions)
    if kind == "rename":
        planned, details = _plan_rename(root, files, options)
    elif kind == "extensions":
        planned, details = _plan_extensions(files, options)

    source_paths = {entry["old"] for entry in planned}
    destinations = set()
    for entry in planned:
        old_path, new_path = entry["old"], entry["new"]
        if not old_path.is_file():
            raise OperationError(f"A file in the preview is no longer available: {_format_path(root, old_path)}")
        if new_path in destinations:
            raise OperationError(f"Two files would receive the same name: {_format_path(root, new_path)}")
        destinations.add(new_path)
        if new_path.exists() and new_path not in source_paths:
            raise OperationError(f"A destination already exists: {_format_path(root, new_path)}")

    return OperationPreview(root, kind, planned, {
        "timestamp": datetime.now().astimezone().isoformat(),
        "target_directory": str(root),
        "separator": details.get("separator"),
        "renamed_files": [
            {
                "original_path": str(entry["old"]),
                "new_path": str(entry["new"]),
                "original_name": entry["old"].name,
                "new_name": entry["new"].name,
            }
            for entry in planned
        ],
    }, 0)


def preview_response(preview):
    return {
        "kind": preview.kind,
        "folder": str(preview.root),
        "totalFiles": len(preview.entries),
        "entries": [
            {
                "old": _format_path(preview.root, entry["old"]),
                "new": _format_path(preview.root, entry["new"]),
            }
            for entry in preview.entries
        ],
    }


def _create_backups(preview, backup_options):
    if not isinstance(backup_options, dict):
        raise OperationError("Backup settings are invalid.")
    values = [backup_options.get(name, False) for name in ("copy", "zip", "log")]
    if any(not isinstance(value, bool) for value in values):
        raise OperationError("Backup options must be enabled or disabled.")
    copy_files, create_zip, create_log = values
    if not (copy_files or create_zip or create_log):
        return []

    app_name = "FilesRenamer" if preview.kind == "rename" else "Exteditor"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    backup_dir = Path.home() / "Desktop" / "FilesEditor" / app_name / "Backup" / timestamp
    try:
        backup_dir.mkdir(parents=True, exist_ok=False)
        if copy_files:
            original_root = backup_dir / "Originals" / preview.root.name
            for entry in preview.entries:
                source = entry["old"]
                destination = original_root / source.relative_to(preview.root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        if create_zip:
            archive = backup_dir / f"{preview.root.name}_backup.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for entry in preview.entries:
                    source = entry["old"]
                    zip_file.write(source, arcname=str(Path(preview.root.name) / source.relative_to(preview.root)))
        if create_log:
            log_name = "rename_log.json" if preview.kind == "rename" else "exteditor_log.json"
            with (backup_dir / log_name).open("w", encoding="utf-8") as log_file:
                json.dump(preview.log_data, log_file, ensure_ascii=False, indent=2)
    except (OSError, zipfile.BadZipFile) as error:
        raise OperationError(f"Could not create the requested backup: {error}") from error
    return [str(backup_dir)]


def apply_preview(preview, backup_options):
    if not preview.entries:
        raise OperationError("There are no changes to apply.")
    source_paths = {entry["old"] for entry in preview.entries}
    destinations = set()
    for entry in preview.entries:
        old_path, new_path = entry["old"], entry["new"]
        if not old_path.is_file():
            raise OperationError(f"A source file is no longer available: {_format_path(preview.root, old_path)}")
        if new_path in destinations:
            raise OperationError(f"Two files would receive the same name: {_format_path(preview.root, new_path)}")
        destinations.add(new_path)
        if new_path.exists() and new_path not in source_paths:
            raise OperationError(f"A destination already exists: {_format_path(preview.root, new_path)}")

    backups = _create_backups(preview, backup_options)
    staged = []
    completed = []
    try:
        # Stage every source first so swaps and cycles cannot overwrite files.
        for entry in preview.entries:
            temporary = entry["old"].with_name(f".files-editor-{uuid.uuid4().hex}.tmp")
            entry["old"].rename(temporary)
            staged.append((temporary, entry["old"], entry["new"]))
        for temporary, original, destination in staged:
            if destination.exists():
                raise OperationError(f"A destination appeared during the operation: {_format_path(preview.root, destination)}")
            temporary.rename(destination)
            completed.append((destination, original))
    except (OSError, OperationError) as error:
        rollback_errors = []
        for current, original in reversed(completed):
            try:
                if current.exists() and not original.exists():
                    current.rename(original)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for temporary, original, _destination in reversed(staged):
            try:
                if temporary.exists() and not original.exists():
                    temporary.rename(original)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        detail = f"File changes were rolled back: {error}"
        if rollback_errors:
            detail += " Rollback also reported: " + "; ".join(rollback_errors)
        raise OperationError(detail) from error

    log_path = None
    if backup_options.get("log") and backups:
        log_name = "rename_log.json" if preview.kind == "rename" else "exteditor_log.json"
        log_path = Path(backups[0]) / log_name

    return {
        "changed": len(preview.entries),
        "backups": backups,
        "log": str(log_path) if log_path else None,
        "undoLog": preview.log_data,
    }
