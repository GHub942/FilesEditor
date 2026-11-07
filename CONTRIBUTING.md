# Contributing

## Development setup

- Python 3.10 or later is required for the web server and tests.
- The web version uses only the Python standard library.
- Node.js is optional and can be used to check the browser script syntax.

## Validation

Run the focused web tests from the project root:

```powershell
python -m unittest discover -s WEB\tests -v
```

Check browser JavaScript syntax with:

```powershell
node --check WEB\app.js
```

## Web interface changes

- Keep all user-visible strings in both `WEB\locales\en.json` and `WEB\locales\fr.json`.
- Use translation keys in `WEB\index.html` and `WEB\app.js`; do not add hard-coded interface copy.
- Preserve local-only operation, preview-before-apply, and collision checks.
- Add or update tests when changing file-operation behavior.

## Pull requests

Describe the behavior change, the checks you ran, and any safety implications for file operations.
