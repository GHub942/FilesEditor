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

Open `http://127.0.0.1:8765`; the exact root URL redirects to the bilingual landing page at `/home`. The sidebar provides an icon-only Home link and an icon-only Settings button side by side. The server binds to the local computer only; keep the terminal window open while using it and press `Ctrl+C` to stop.

The web tools have direct URLs: `/tools/01` (File Renamer), `/tools/02` (Extension Editor), and `/tools/undo` (Undo Changes). Open **Settings** from the navigation; it is a modal represented by the current URL with `?settings=true`.

The interface supports English and French. In Settings, **Do not save preferences** is enabled by default; reloading then resets the language to English. Disable it to save the language and persistence choice in this browser. The server also disables HTTP caching. File-operation previews show 25 entries per page, and unknown web routes display a localized not-found page.

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

The workflow also runs Chromium browser checks for desktop/mobile layouts, active navigation, keyboard focus, and icon-button tooltips. To run these checks locally, install the test-only dependency with `python -m pip install -r requirements-test.txt` and install Chromium with `python -m playwright install chromium`.

## Safety

Use the web app locally only; it is not intended for public network deployment. Review each preview and keep a backup of important files before applying changes.
