# 🏈 CFB Data Tool

A friendly **desktop app** for capturing College Football data from your screen using OCR + computer vision — no terminal, no config files. The first data type it captures is **recruit cards**; the engine is built around pluggable *scrape profiles* so other data (rosters, player stats, schedules) and future game versions can be added without re-architecting.

This is the GUI successor to the [cf26-recruit-scraper](https://github.com/patches822/cf26-recruit-scraper) CLI, rebuilt for non-technical users.

> **Status:** ✅ Feature-complete (v0.1.3). Engine, UI, calibration editor, data viewer, inline correction, auto-capture, and installers for Windows and macOS are all in place. New users should start with [QUICKSTART.md](QUICKSTART.md).

## Features

- **Visual ROI editor + auto-calibration** — drag/resize the capture regions over a live screenshot; auto-scale to any resolution (no more hand-editing pixel offsets).
- **Built-in data viewer/export** — sortable, filterable, de-duplicated table backed by SQLite; export to CSV (import into your spreadsheet of choice).
- **Live OCR confidence + inline correction** — low-confidence fields are flagged so you can fix a misread before saving.
- **Auto-capture / batch mode** — optionally detect new cards and queue them for review. Invalid scans stay in the queue after saving so you can fix or discard them.
- **Abilities & mentals** — scrapes ability names with tier detection (Bronze/Silver/Gold/Platinum) and mental traits from the recruit card.
- **One-click install** — Windows installer (PyInstaller + Inno Setup) and macOS `.app` bundle (+ optional DMG).

## Architecture

```txt
app/ui/                PySide6 desktop UI (Capture, Calibrate, Data, Settings tabs)
app/core/ocr/          OCR behind an interface (RapidOCR/ONNX backend)
app/core/processor.py  star count (template match) + gem/bust + ability tier (HSV) — CV, not OCR
app/core/profiles/     ScrapeProfile interface + registry; recruits is profile #1
app/core/calibration.py ROI presets keyed by (game_version, profile); resolution scaling
app/core/engine.py     scan(image) -> ScanResult  (produces results; never saves)
app/core/capture.py    screen capture via mss (BGR numpy arrays)
app/core/sound.py      cross-platform sound playback (.wav / .aiff)
app/io/                SQLite record store + CSV export
app/config/presets/    JSON ROI presets (e.g. cfb26/recruits.json)
```

OCR was switched from EasyOCR to **RapidOCR (ONNX)** to drop the PyTorch dependency, shrinking the install from ~2 GB to ~250 MB and removing the GPU requirement.

## Developer setup

Requires **Python 3.12+**.

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -e .
```

### Tests

Tests are standalone scripts (not pytest-based). Run them directly:

```bash
# Smoke tests (headless, no screenshots needed)
python tests/smoke_autocapture.py       # auto-capture + review queue
python tests/smoke_data.py              # data tab + store

# Smoke tests (need fixture screenshots in tests/fixtures/screenshots/)
python tests/smoke_ui.py                # basic UI construction
python tests/smoke_calibration.py       # calibration preset loading/scaling

# Or run all smoke tests via pytest
pytest tests/test_smoke.py -v
```

#### OCR accuracy harness

Runs the engine over a folder of recruit-card screenshots and reports per-image pass/fail plus a per-field failure breakdown. Results are written as JSON to `tests/reports/`.

```bash
# Uses the committed sample in tests/fixtures/screenshots/ by default.
python tests/test_accuracy.py

# Point at a larger screenshot corpus (not committed):
set CFB_SCREENSHOTS=C:\path\to\screenshots   # Windows
export CFB_SCREENSHOTS=/path/to/screenshots  # macOS / Linux
python tests/test_accuracy.py
```

#### Debug OCR for a single image

```bash
python tests/debug_ocr.py path/to/screenshot.png
```

## Building the Windows installer

End users get a double-click installer — no Python required. To build it:

```powershell
pip install pyinstaller          # in the venv
powershell -File packaging\build.ps1
```

This runs PyInstaller (`packaging/cfbdatatool.spec`) to produce a one-folder bundle at
`dist\CFBDataTool\` (~320 MB — RapidOCR/ONNX keeps it far smaller than a PyTorch build),
then, if [Inno Setup 6](https://jrsoftware.org/isdl.php) is installed, packages it into
`dist\installer\CFBDataTool-Setup.exe` (no-admin, per-user install with Start Menu +
desktop shortcuts).

Verify a bundle without launching the UI:

```powershell
$env:CFB_SMOKE = "1"; .\dist\CFBDataTool\CFBDataTool.exe
Get-Content .\dist\CFBDataTool\smoke_result.txt   # should say "SMOKE OK"
```

## Building the macOS app

```bash
pip install pyinstaller       # in the venv
python packaging/gen_icons.py  # generate icon.icns + icon.ico from icon.png (one-time)
bash packaging/build_mac.sh
```

This produces `dist/CFBDataTool.app`. If [`create-dmg`](https://github.com/create-dmg/create-dmg) is installed (`brew install create-dmg`), the script also builds `dist/installer/CFBDataTool.dmg` with a drag-to-Applications layout.

> **Note:** The global scan hotkey requires Accessibility permission on macOS (System Settings > Privacy & Security > Accessibility). Without it, use the on-screen **Scan** button.

End-user instructions live in [QUICKSTART.md](QUICKSTART.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

Copyright (C) 2026 Tyler Patchoski

Licensed under the **GNU General Public License v3.0 or later** — see [LICENSE](LICENSE). This program comes with **NO WARRANTY**.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Electronic Arts Inc. "College Football" and related marks are trademarks of Electronic Arts. This tool only reads pixels from your own screen — it does not modify the game or access game memory.
