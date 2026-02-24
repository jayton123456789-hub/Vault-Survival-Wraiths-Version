from __future__ import annotations

import json
from pathlib import Path

from bit_life_survival.core.persistence import load_save_data, storage_used


def test_old_save_materials_in_storage_are_migrated(tmp_path: Path) -> None:
    payload = {
        "vault": {
            "storage": {
                "scrap": 7,
                "cloth": 3,
                "plastic": 4,
                "metal": 2,
                "backpack_basic": 1,
            },
            "blueprints": [],
            "upgrades": {},
            "tav": 10,
            "vaultLevel": 1,
            "citizen_queue": [],
            "current_citizen": None,
            "milestones": [],
            "run_counter": 0,
            "last_run_seed": None,
            "last_run_distance": 0.0,
            "last_run_time": 0,
            "claw_rng_state": 1,
            "claw_rng_calls": 0,
            "settings": {
                "skip_intro": False,
                "intro_use_cinematic_audio": True,
                "seeded_mode": True,
                "base_seed": 1337,
                "seen_run_help": False,
            },
        }
    }
    save_path = tmp_path / "legacy_save.json"
    save_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    loaded = load_save_data(save_path)
    vault = loaded.vault
    assert vault.materials["scrap"] == 7
    assert vault.materials["cloth"] == 3
    assert vault.materials["plastic"] == 4
    assert vault.materials["metal"] == 2
    assert "scrap" not in vault.storage
    assert "cloth" not in vault.storage
    assert "plastic" not in vault.storage
    assert "metal" not in vault.storage
    assert storage_used(vault) == 1
