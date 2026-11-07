# Files Editor Web

A local web interface for the file renamer, extension editor, and undo tools in the parent project. The Python standard-library server performs file operations on the computer running the app; the browser provides configuration, previews, and results.

## Requirements

- Python 3.10 or later
- A modern desktop browser

No third-party packages, external services, or build step are required.

## Run

From the project directory:

```powershell
python .\web\app.py
```

The app opens at `http://127.0.0.1:8765`. Keep the terminal open while using it; press `Ctrl+C` to stop the server.

## Features

- Rename files by category, with configurable prefixes, separator, category filters, and number padding.
- Change file extensions by media category. This changes names only; it does not convert file contents.
- Scan a folder and optionally its subfolders, excluding common development and temporary directories by default.
- Preview planned changes before applying them.
- Create full-copy and ZIP backups, and JSON undo logs.
- Restore a previous rename or extension operation from its JSON log.

## Safety

The server listens only on the local loopback interface. File changes are restricted to the explicitly entered target folder, and operations require a separate confirmation after preview. Existing destinations are never overwritten. Backups and logs are written under `Desktop\FilesEditor`.

The app is intended for local use, not deployment to a public network. Keep backups of important files before making changes.
