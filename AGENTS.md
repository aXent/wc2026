# Repository Guidelines

## Project Structure & Module Organization

This repository builds a static Dutch WK 2026 cheat sheet/PWA. `generate.py` fetches TheSportsDB event data, computes group standings, and renders `template.html` into `index.html`. Keep reusable markup and placeholders in `template.html`; treat `index.html` as generated output. The generator substitutes five placeholders in `template.html`: `{{DATE}}`, `{{GROUPS}}` (group-card HTML), and `{{POP_DATA}}`, `{{FX_DATA}}`, `{{TL_DATA}}` (inline JS data objects for the standings popover, the fixtures/Speelkalender, and per-match goals/cards). Adding or renaming a placeholder requires matching changes in both files. Root PNG files (`icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png`) and `manifest.json` provide PWA assets. `.github/workflows/update.yml` runs the scheduled regeneration job (every 30 minutes via `*/30 * * * *`, plus manual `workflow_dispatch`) and commits `index.html` and `data.json` when either changed.

`data.json` is a committed cache of per-match goal/card timelines (`lookuptimeline.php`). A finished game's timeline is immutable, so it's fetched once (keyed by `idEvent`) and reused on later runs — committing it is what lets the cache survive the ephemeral Actions runner. Net API cost per run is one `eventsseason` call plus one timeline call per *newly* finished match. `{{TL_DATA}}` is keyed by `"<homeFlag>_<awayFlag>_<day>/<month>"`, the same key the client recomputes from each Speelkalender row to attach goals/cards; if you change that key, change it in `render_tl_data` and the template's `tlKey` together.

## Build, Test, and Development Commands

- `TSDB_KEY=<premium-key> python3 generate.py`: regenerate `index.html`; the free TheSportsDB key is too limited for the full schedule.
- `python3 -m http.server 8000`: serve the static site locally; open `http://localhost:8000`.
- `python3 -m py_compile generate.py`: run a fast syntax check for the generator.
- `git diff -- index.html`: review generated output before committing.

## Coding Style & Naming Conventions

Use Python 3.12-compatible standard-library code; the workflow installs Python 3.12 and no dependencies. Follow the existing compact constants style in `generate.py` (`GROUPS`, `TEAMS`, `OUTPUT`) and snake_case for functions. Keep Dutch user-facing copy consistent with the current site. Preserve UTF-8 encoding for team names, flags, and Belgian time labels. Avoid manual edits to generated HTML unless the same change also belongs in `template.html` or `generate.py`.

## Testing Guidelines

There is no separate automated test suite. Validate changes by running `python3 -m py_compile generate.py`, then `TSDB_KEY=<premium-key> python3 generate.py`. The generator hard-fails (`sys.exit`) unless it assembles all 72 group matches, so an incomplete or free-tier key produces no output rather than a partial page — a successful run is itself a check. After regeneration, inspect the console output for warnings about unknown teams (add missing aliases to `TEAMS`) and review `index.html` in a browser. For template or CSS changes, test both desktop and mobile widths and verify that the PWA manifest still references existing icon files.

## Commit & Pull Request Guidelines

Git history uses short, imperative messages such as `update`, plus scheduled bot commits like `Auto-update standen (YYYY-MM-DD HH:MM UTC)`. Prefer concise commit messages that describe the changed behavior, for example `update group rendering` or `adjust schedule refresh`. Pull requests should include a short summary, validation commands run, and screenshots for visible UI changes. Link related issues when available and call out any data-source or API-key assumptions.

## Security & Configuration Tips

Do not commit private API keys. Use the `TSDB_KEY` environment variable locally and the GitHub Actions `TSDB_KEY` secret for scheduled runs. The fallback key `123` is for smoke tests only and cannot generate a complete schedule.
