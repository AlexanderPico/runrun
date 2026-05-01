# RunRun

RunRun is a local-first static race diary for Athlinks athlete 92157185 (Elisa Park). It turns a checked-in data snapshot into a single-page HTML experience with weather-aware performance summaries, yearly mileage views, and race-result browsing that can open directly from the filesystem.

## Repo layout

- `index.html` — primary single-page diary UI
- `data/athlete-diary.js` — file://-friendly data mirror used by the app
- `data/athlete-diary.json` — canonical structured diary snapshot
- `scripts/build_diary_data.py` — rebuilds the diary snapshot from Athlinks + Open-Meteo
- `tests/index.html` — browser smoke page for manual spot checks
- `tests/smoke.test.mjs` — Node built-in smoke tests for repo wiring and dataset integrity

## Local validation

```bash
npm test
python3 -m py_compile scripts/build_diary_data.py
```

The Node smoke suite checks that the checked-in diary mirror exposes the expected athlete summary, keeps results newest-first, wires `index.html` to the local data files, and documents the validation path.

## GitHub Actions

`.github/workflows/ci.yml` runs the same local validation commands on pushes and pull requests to `main`:

- `npm test`
- `python3 -m py_compile scripts/build_diary_data.py`

This keeps the static diary and rebuild script from drifting silently.
