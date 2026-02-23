from __future__ import annotations

from pathlib import Path

from bit_life_survival.app.services.settings_store import SettingsStore


def test_settings_store_read_write(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    loaded = store.load()
    assert loaded["gameplay"]["skip_intro"] is False

    loaded["gameplay"]["show_advanced_overlay"] = True
    loaded["video"]["resolution"] = [1600, 900]
    loaded["audio"]["master"] = 0.5
    store.save(loaded)

    reloaded = store.load()
    assert reloaded["gameplay"]["show_advanced_overlay"] is True
    assert reloaded["video"]["resolution"] == [1600, 900]
    assert reloaded["audio"]["master"] == 0.5
