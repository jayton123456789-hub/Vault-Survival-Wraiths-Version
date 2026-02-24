from __future__ import annotations

from pathlib import Path

from bit_life_survival.app.services.saves import SaveService


def test_save_slot_create_and_load_roundtrip(tmp_path: Path) -> None:
    service = SaveService(tmp_path / "saves", slot_count=3)
    created = service.create_new_game(slot=1, base_seed=2026)
    created.vault.tav = 42
    created.vault.last_run_distance = 17.5
    created.vault.last_run_time = 9
    service.save_slot(1, created)

    loaded = service.load_slot(1)
    assert loaded.vault.tav == 42
    assert loaded.vault.last_run_distance == 17.5
    assert loaded.vault.last_run_time == 9

    summaries = service.list_slots()
    slot1 = next(summary for summary in summaries if summary.slot == 1)
    assert slot1.occupied is True
    assert slot1.slot_name == "Slot 1"
    assert slot1.tav == 42
    assert slot1.last_distance == 17.5
    assert slot1.last_time == 9
