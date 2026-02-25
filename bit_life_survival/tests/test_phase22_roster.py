from __future__ import annotations

from bit_life_survival.core.models import SAVE_VERSION
from bit_life_survival.core.persistence import (
    citizen_queue_target,
    compute_roster_capacity,
    create_default_vault_state,
    on_run_finished,
    transfer_claw_pick_to_roster,
)
from bit_life_survival.core.save_system import migrate_save


def test_migrate_v2_to_v3_moves_overflow_to_reserve_and_sets_capacities() -> None:
    queue = [
        {"id": f"q{i}", "name": f"Q{i}", "quirk": "Test", "kit": {}, "loadout": {}}
        for i in range(12)
    ]
    payload = {
        "save_version": 2,
        "vault": {
            "storage": {},
            "materials": {"scrap": 0, "cloth": 0, "plastic": 0, "metal": 0},
            "blueprints": [],
            "upgrades": {"drone_bay_level": 0},
            "tav": 0,
            "vaultLevel": 1,
            "citizen_queue": queue,
            "deploy_roster": [],
            "citizen_reserve": [],
            "current_citizen": None,
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
    vault = migrated["vault"]
    assert migrated["save_version"] == SAVE_VERSION
    assert vault["citizen_queue_capacity"] == 4
    assert vault["deploy_roster_capacity"] == 1
    assert len(vault["citizen_queue"]) == 4
    assert len(vault["citizen_reserve"]) == 8


def test_claw_transfer_to_roster_and_lifecycle_rules() -> None:
    vault = create_default_vault_state(base_seed=101)
    assert len(vault.deploy_roster) == 0
    picked = transfer_claw_pick_to_roster(vault, preview_count=5)
    assert picked.id == vault.active_deploy_citizen_id
    assert len(vault.deploy_roster) == 1
    assert len(vault.citizen_queue) == citizen_queue_target(vault)

    # Retreat keeps the active citizen available for deploy.
    on_run_finished(vault, result="retreat", citizen_id=picked.id)
    assert any(c.id == picked.id for c in vault.deploy_roster)

    # Death removes the active citizen from deploy roster.
    on_run_finished(vault, result="death", citizen_id=picked.id)
    assert all(c.id != picked.id for c in vault.deploy_roster)


def test_capacity_growth_is_bounded() -> None:
    vault = create_default_vault_state(base_seed=999)
    vault.vault_level = 6
    vault.tav = 420
    vault.upgrades["drone_bay_level"] = 5
    assert 4 <= citizen_queue_target(vault) <= 12
    assert 1 <= compute_roster_capacity(vault) <= 8
