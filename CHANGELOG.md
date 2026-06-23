# Changelog

All notable changes to CFB Data Tool are documented here.

## [0.1.0] — 2026-06-23

First public release. Feature-complete desktop app for capturing recruit cards.

### Added

- **Profile-driven capture engine** — pluggable `ScrapeProfile` interface with recruits as the first profile. OCR (RapidOCR/ONNX) + computer-vision pipeline (star counting via template match, gem/bust via HSV).
- **PySide6 desktop UI** — tabbed interface (Capture, Calibrate, Data, Settings) replacing the original CLI.
- **Visual ROI editor + auto-calibration** — drag/resize capture regions over a live screenshot; auto-scale bundled 1440p preset to any resolution.
- **SQLite data viewer + CSV export** — sortable, filterable, de-duplicated table; re-scanning a recruit updates instead of duplicating.
- **Live OCR confidence + inline correction** — low-confidence fields are flagged; click to fix before saving.
- **Auto-capture / batch mode** — detects new recruit cards via frame-diff and queues them for review.
- **Windows installer** — PyInstaller + Inno Setup; per-user install, no admin required (~320 MB).
- **Configurable settings** — scan hotkey, success/fail sounds, confidence threshold, auto-save.
