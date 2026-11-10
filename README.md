# FilesEditor Legacy

> **This repository is frozen.** The project is complete and will not receive
> further modifications. Active development has moved to
> [FilesEditor](https://github.com/GHub942/FilesEditor) — please use that repository
> instead.

## What it is

A local file-management toolkit. It ships two versions:

- **CLI** — interactive Python command-line utilities for category-based file
  renaming, extension changes, and restoration from JSON undo logs.
- **WEB** — a local browser interface (Python standard library only) for
  renaming files, changing filename extensions, and restoring changes.

Both versions work with files on the computer where they are run. The web
version has no third-party dependencies or build step.

Features:

- Preview every change before applying it, with collision protection
- Full-copy or ZIP backups and optional JSON undo logs under `Desktop\FilesEditor`
- English and French interface, system/light/dark/high-contrast themes
- Searchable, paginated previews and reusable rename presets
- Guided restore of the latest 50 operations

## Requirements

- Python 3.10+ (standard library only — no pip installs)
- A modern browser for the web version

## Usage

Web version — from the `WEB/` folder, either:

```bash
./start.sh        # Linux / macOS / Git Bash
start.bat         # Windows
```

or manually:

```bash
python app.py
```

Then open http://127.0.0.1:8765 — the root URL redirects to the bilingual
landing page at `/home`. Stop with `Ctrl+C` or by closing the terminal.

CLI version — run a script from the project root, for example:

```bash
python CLI/renamer.py
python CLI/exteditor.py
python CLI/undo_renamer.py
python CLI/undo_exteditor.py
```

The CLI tools prompt for their options and target folders.

## Files

| Path              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| `CLI/`            | Original interactive Python utilities + undo tools  |
| `WEB/`            | Local web app: `app.py`, `app.js`, `file_operations.py`, locales, tests |
| `WEB/start.bat`   | Windows launcher                                     |
| `WEB/start.sh`    | Linux / macOS / Git Bash launcher                    |
| `LICENSE.md`      | MIT license                                          |

## License

MIT — see [LICENSE.md](LICENSE.md).
