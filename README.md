# 🏈 CFB Data Tool

A friendly **desktop app** for capturing College Football data from your screen using OCR + computer vision — no terminal, no config files. The first data type it captures is **recruit cards**; the engine is built around pluggable *scrape profiles* so other data (rosters, player stats, schedules) and future game versions can be added without re-architecting.

This is the GUI successor to the [cf26-recruit-scraper](https://github.com/patches822/cf26-recruit-scraper) CLI, rebuilt for non-technical users.

> **Status:** 🚧 Early development. The capture **engine** (Phase 1) is in place — OCR/CV extraction, the profile system, calibration presets, and a headless accuracy harness. The PySide6 UI is next. See [docs/cfb-data-tool-plan.md](../cf26-recruit-scraper/docs/cfb-data-tool-plan.md) in the original repo for the full plan.

## Planned features

- **Visual ROI editor + auto-calibration** — drag/resize the capture regions over a live screenshot; auto-scale to any resolution (no more hand-editing pixel offsets).
- **Built-in data viewer/export** — sortable, filterable, de-duplicated table backed by SQLite; export to CSV (import into your spreadsheet of choice).
- **Live OCR confidence + inline correction** — low-confidence fields are flagged so you can fix a misread before saving.
- **Auto-capture / batch mode** — optionally detect new cards and queue them for review.
- **One-click install** — packaged Windows installer (PyInstaller + Inno Setup); macOS/Linux later.

## Architecture

```
app/core/ocr/        OCR behind an interface (RapidOCR/ONNX backend)
app/core/processor   star count (template match) + gem/bust (HSV) — CV, not OCR
app/core/profiles/   ScrapeProfile interface + registry; recruits is profile #1
app/core/calibration ROI presets keyed by (game_version, profile); resolution scaling
app/core/engine      scan(image) -> ScanResult  (produces results; never saves)
app/io/              SQLite record store + CSV export
app/config/presets/  JSON ROI presets (e.g. cfb26/recruits.json)
```

OCR was switched from EasyOCR to **RapidOCR (ONNX)** to drop the PyTorch dependency, shrinking the install from ~2 GB to ~250 MB and removing the GPU requirement.

## Developer setup

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows (use source .venv/bin/activate elsewhere)
pip install -e .
```

### Run the accuracy harness

```bash
# Uses tests/fixtures/screenshots by default.
python tests/test_accuracy.py

# Point at the full screenshot corpus (not committed — it's large):
set CFB_SCREENSHOTS=D:\path\to\cf26-recruit-scraper\screenshots   # Windows
python tests/test_accuracy.py
```

It prints a per-image pass/fail table plus a per-field failure breakdown, and writes a JSON report to `tests/reports/`.

### Inspect raw OCR for one image

```bash
python tests/debug_ocr.py path/to/screenshot.png
```

## License

Copyright (C) 2026 Tyler Patchoski

Licensed under the **GNU General Public License v3.0 or later** — see [LICENSE](LICENSE). This program comes with **NO WARRANTY**.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Electronic Arts Inc. "College Football" and related marks are trademarks of Electronic Arts. This tool only reads pixels from your own screen — it does not modify the game or access game memory.
