from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bit_life_survival.core.settings import default_settings, merge_settings

DEFAULT_SETTINGS: dict[str, Any] = default_settings()


def _deep_copy_defaults() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    return merge_settings(data)


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
