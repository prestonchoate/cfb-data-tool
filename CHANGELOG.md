# Changelog

All notable changes to CFB Data Tool are documented here.

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
