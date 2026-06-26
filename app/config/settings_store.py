# SPDX-License-Identifier: GPL-3.0-or-later
"""User settings persisted as JSON in the OS config dir (never edited by hand).

Phase 2 surfaces a subset (output path, monitor, hotkey, sounds, confidence
threshold); the Settings tab grows alongside later phases.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from ..core.sound import default_fail, default_success, is_sound_file

APP_NAME = "cfb-data-tool"
CONFIG_DIR = Path(user_config_dir(APP_NAME, appauthor=False))
DATA_DIR = Path(user_data_dir(APP_NAME, appauthor=False))
SETTINGS_PATH = CONFIG_DIR / "settings.json"


@dataclass
class Settings:
    game_version: str = "cfb26"
    profile: str = "recruits"
    monitor_number: int = 1
    output_csv_path: str = str(DATA_DIR / "recruits_scraped.csv")
    sqlite_path: str = str(DATA_DIR / "cfb_data.db")
    hotkey: str = "s"
    use_sounds: bool = True
    success_sound: str = field(default_factory=default_success)  # .wav path
    fail_sound: str = field(default_factory=default_fail)
    auto_save_valid: bool = False           # save valid scans without review
    confidence_threshold: float = 0.80      # below this a field is flagged

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                s = cls(**known)
                # Migrate old system-alias sounds to real .wav files.
                if not is_sound_file(s.success_sound):
                    s.success_sound = default_success()
                if not is_sound_file(s.fail_sound):
                    s.fail_sound = default_fail()
                return s
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def ensure_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
