"""Shared helpers for the FilesEditor command-line tools."""

import os
import sys
from pathlib import Path

DEFAULT_EXCLUDED_DIRS = {
    ".venv", "venv", "env", ".env",
    "temp", "tmp", ".temp", ".tmp",
    "node_modules", ".git", "__pycache__", ".idea", ".vscode",
}


def clear_terminal():
    """Clear the terminal for the current OS."""
    os.system("cls" if os.name == "nt" else "clear")


def print_progress_bar(current, total, filename, step_name="Progress", bar_length=25):
    """Print an animated progress bar with percentage, step, and filename."""
    percent = (current / total) * 100 if total > 0 else 100
    filled = int(bar_length * current // total) if total > 0 else bar_length
    bar = "█" * filled + "-" * (bar_length - filled)
    display_name = filename if len(filename) <= 30 else filename[:27] + "..."
    sys.stdout.write(
        f"\r[{bar}] {percent:5.1f}% ({current}/{total}) | {step_name:<18} : {display_name:<30}"
    )
    sys.stdout.flush()
    if current == total:
        print()


def select_target_directory():
    """Ask whether to process the current folder or a custom absolute path."""
    current_dir = Path.cwd()
    print(f"Current folder: {current_dir}")
    choice = input("Process this folder? (Y/n) : ").strip().lower()
    if choice in ("", "y", "yes"):
        return current_dir

    while True:
        custom_path = input("Enter the absolute folder path: ").strip().strip('"\'')
        target = Path(custom_path)
        if target.is_dir():
            return target
        print("❌ Invalid folder. Please try again.\n")


def collect_files(target_dir, recursive, excluded_dirs, skip_names=(), skip_prefixes=()):
    """Collect files, optionally recursing while pruning excluded directories."""
    files = []
    subfolder_count = 0

    def keep(path):
        name = path.name
        return name not in skip_names and not name.startswith(skip_prefixes)

    if recursive:
        for root, dirs, filenames in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            if root != str(target_dir):
                subfolder_count += 1
            for fn in filenames:
                path = Path(root) / fn
                if keep(path):
                    files.append(path)
    else:
        files = [f for f in target_dir.iterdir() if f.is_file() and keep(f)]

    return files, subfolder_count
