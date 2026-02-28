from __future__ import annotations

from bit_life_survival.core.models import SAVE_VERSION
from bit_life_survival.core.save_system import migrate_save


def test_migrate_v3_to_v4_adds_ui_settings_defaults() -> None:
    payload = {
        "save_version": 3,
        "vault": {
            "materials": {"scrap": 10, "cloth": 8, "plastic": 5, "metal": 3},
            "storage": {"backpack_basic": 1},
            "blueprints": [],
            "upgrades": {"drone_bay_level": 0},
            "tav": 0,
            "vaultLevel": 1,
            "citizen_queue": [],
            "deploy_roster": [],
            "citizen_reserve": [],
            "current_citizen": None,
            "active_deploy_citizen_id": None,
            "citizen_queue_capacity": 4,
            "deploy_roster_capacity": 1,
            "milestones": [],
            "run_counter": 0,
            "last_run_seed": 1337,
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
        },
    }

    migrated = migrate_save(payload)
    assert migrated["save_version"] == SAVE_VERSION == 4
    settings = migrated["vault"]["settings"]
    assert settings["theme_preset"] == "ember"
    assert settings["font_scale"] == 1.0
    assert settings["show_tooltips"] is True
