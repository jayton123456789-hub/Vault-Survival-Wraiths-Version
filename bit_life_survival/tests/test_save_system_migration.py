from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.models import RUNNER_EQUIP_SLOTS, SAVE_VERSION
from bit_life_survival.core.save_system import SlotStorage, migrate_save


def test_migrate_legacy_payload_sets_version_and_hydrates_fields() -> None:
    legacy = {
        "vault": {
            "storage": {"scrap": 5, "cloth": 2, "backpack_basic": 1},
            "citizen_queue": [{"id": "c1", "name": "Ari", "quirk": "Keeps watch", "kit": {"scrap": 1}}],
            "current_citizen": {"id": "c2", "name": "Jax", "quirk": "Fast walker"},
        }
    }
    migrated = migrate_save(legacy)

    assert migrated["save_version"] == SAVE_VERSION
    vault = migrated["vault"]
    assert vault["materials"]["scrap"] == 5
    assert vault["materials"]["cloth"] == 2
    assert "scrap" not in vault["storage"]
    assert "cloth" not in vault["storage"]
    assert vault["storage"]["backpack_basic"] == 1

    queue_citizen = vault["citizen_queue"][0]
    for slot in RUNNER_EQUIP_SLOTS:
        assert slot in queue_citizen["loadout"]
    current = vault["current_citizen"]
    for slot in RUNNER_EQUIP_SLOTS:
        assert slot in current["loadout"]


def test_slot_storage_clamps_slot_count_to_supported_range(tmp_path: Path) -> None:
    low = SlotStorage(tmp_path / "low", slot_count=1)
    high = SlotStorage(tmp_path / "high", slot_count=9)

    assert low.slot_ids == (1, 2, 3)
    assert high.slot_ids == (1, 2, 3, 4, 5)
