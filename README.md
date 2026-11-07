# Files Editor

Files Editor contains two local file-management tools:

- **CLI** — the original interactive Python command-line utilities.
- **WEB** — a browser interface for renaming files, changing filename extensions, and restoring changes from JSON undo logs.

Both versions work with files on the computer where they are run. The web version uses Python's standard library and has no third-party dependencies or build step.

## Web version

Requirements: Python 3.10 or later and a modern browser.

From the project directory, start the local web app:

```powershell
python .\WEB\app.py
```

Open `http://127.0.0.1:8765`. The server binds to the local computer only; keep the terminal window open while using it and press `Ctrl+C` to stop.

The web interface supports English and French. Open **Settings** to choose a language; the preference is stored in the current browser on the current device. File-operation previews show 25 entries per page, and unknown web routes display a localized not-found page.

The web app previews file operations before applying them, can make full-copy or ZIP backups, and saves optional JSON undo logs under `Desktop\FilesEditor`. Changing an extension changes the filename only; it does not convert the file contents.

## CLI version

The original scripts are in [CLI/](./CLI/):

- `renamer.py` — category-based file renaming.
- `exteditor.py` — category-based extension renaming.
- `undo_renamer.py` — restore names from a rename log.
- `undo_exteditor.py` — restore extensions from an extension log.

Run a script from the project root, for example:

```powershell
python .\CLI\renamer.py
```

The CLI tools prompt for their options and target folders.

## Tests

Run the web file-operation tests from the project root:

```powershell
python -m unittest discover -s WEB\tests -v
```

## Safety

Use the web app locally only; it is not intended for public network deployment. Review each preview and keep a backup of important files before applying changes.
