# Changelog

## Unreleased

- Fix GitHub Actions test discovery and add automated desktop/mobile browser checks for active navigation, keyboard focus, and tooltips.
- Highlight the Home control on `/home`, the Settings control while its modal is open, and the active file tool; localize icon-button tooltips.
- Replace the Settings sidebar mark with a clear gear icon and expand the adjacent Home and Settings buttons across the sidebar width.
- Add a bilingual landing page at `/home` and direct URLs for all three web tools.
- Redirect `/` to `/home` and represent the Settings modal with `?settings=true`.
- Add adjacent icon-only Home and Settings controls to the web sidebar.
- Add a default-on preference privacy option; enabled mode forgets the language on reload, disabled mode saves it locally.
- Preserve the local-only server and disable HTTP caching for web responses.
- Organize the repository into `CLI/`, `WEB/`, and root-level project documentation.
- Add English and French web-interface translations and a language settings page.
- Keep project-wide ignore rules and documentation at the repository root.

## 1.0.0

- Add a local web interface for renaming files, changing filename extensions, and undoing changes.
- Preserve the original interactive Python CLI tools.
