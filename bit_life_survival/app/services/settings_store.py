from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "gameplay": {
        "skip_intro": False,
        "show_advanced_overlay": False,
        "confirm_retreat": True,
        "save_slots": 3,
        "tutorial_completed": False,
        "replay_tutorial": False,
    },
    "video": {
        "fullscreen": False,
        "resolution": [1280, 720],
        "ui_scale": 1.0,
    },
    "audio": {
        "master": 1.0,
        "music": 0.8,
        "sfx": 0.9,
    },
    "controls": {
        "continue": "C",
        "log": "L",
        "retreat": "R",
        "quit": "Q",
        "help": "H",
    },
}


def _deep_copy_defaults() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_copy_defaults()
    for section, section_values in data.items():
        if section not in merged or not isinstance(section_values, dict):
            continue
        for key, value in section_values.items():
            if key in merged[section]:
                merged[section][key] = value
    return merged


class SettingsStore:
    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path

    def load(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            settings = _deep_copy_defaults()
            self.save(settings)
            return settings
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        settings = _merge_defaults(payload)
        self.save(settings)
        return settings

    def save(self, settings: dict[str, Any]) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
