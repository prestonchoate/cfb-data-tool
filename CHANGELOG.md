# Changelog

All notable changes to CFB Data Tool are documented here.

## [0.1.3] — 2026-06-29

### Added

- **Ability & mental trait scraping** — recruit scans now extract up to 5 abilities and 3 mental traits, each with their tier (Bronze / Silver / Gold / Platinum) detected via HSV icon-color classification. OCR results are fuzzy-matched against a bundled ability table keyed by position + archetype for higher accuracy. The result card shows editable name + tier dropdown for each ability and mental.
- **Missing-attribute correction slots** — the result card now renders empty attribute rows (with a dropdown of remaining attribute names and a value input) when a scan returns fewer attributes than expected for the position, making it easy to fill in missed fields without re-scanning.
- **Automatic schema migration** — existing SQLite databases are transparently upgraded with new columns (abilities, mentals) on first load, so users upgrading from earlier versions keep their data.
- **Calibration preset merging** — when new ROI keys are added to a bundled preset (e.g. `abilities`, `mentals`), they are automatically merged into saved user calibrations so new features work without re-calibrating.

### Fixed

- **"Save All" keeps invalid scans in queue** — previously, "Save All to Collection" silently discarded records that failed validation. Now only valid recruits are saved; invalid ones remain in the queue for correction or removal.

### Changed

- **Expanded recruit schema** — the CSV/SQLite schema now includes `ABILITY_1–5`, `ABILITY_1_LEVEL–5_LEVEL`, `MENTAL_1–3`, and `MENTAL_1_LEVEL–3_LEVEL` columns between basic info and attributes.
- **Documentation refresh** — README expanded with ability/mental feature description and reorganized test instructions; QUICKSTART updated with save-all behavior clarification; updated screenshots.

---

## [0.1.2] — 2026-06-26

### Added

- **macOS support** — cross-platform sound playback (`.aiff` via `afplay` on macOS), PyInstaller `.app` bundle, optional DMG packaging via `create-dmg`, and CI smoke tests on macOS.
- **Snapshot review for auto-capture** — each auto-captured recruit now caches the screen frame at scan time. Clicking a queued recruit pauses the live preview and shows the original screenshot with a "SNAPSHOT" badge, making it easy to compare OCR results against the source. A "Back to Live" button resumes the feed.

### Fixed

- **Star template matching fallback** — when the scaled star template exceeds the ROI dimensions, it is now shrunk to fit rather than falling back to less accurate contour detection.

### Changed

- Python version requirement raised to **3.12+**.

---

## [0.1.1] — 2026-06-24

### Added

- **Update checker** — checks GitHub Releases on launch and shows a banner when a newer version is available.

### Fixed

- **Scan crash at non-base resolutions** — the star-rating template (captured at 1440p) is now scaled to match the user's actual resolution, fixing a `matchTemplate` assertion failure when the capture region was smaller than the template.
- **Window expanding to full screen width on scan** — the result card is now scrollable, so populating scan results no longer forces the window wider (fixes capture-card setups where the scraper shares screen space with a capture utility).

---

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
