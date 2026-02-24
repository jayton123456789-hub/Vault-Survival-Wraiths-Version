from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.models import SaveData
from bit_life_survival.core.save_system import DEFAULT_SLOT_COUNT, SlotStorage, SlotSummary, normalize_slot_count


class SaveService:
    def __init__(self, saves_dir: Path, slot_count: int = DEFAULT_SLOT_COUNT) -> None:
        self.saves_dir = saves_dir
        self.slot_count = normalize_slot_count(slot_count)
        self._slots = SlotStorage(saves_dir, slot_count=self.slot_count)
        self.slot_ids = self._slots.slot_ids

    def list_slots(self) -> list[SlotSummary]:
        return self._slots.list_slots()

    def slot_exists(self, slot: int) -> bool:
        return self._slots.slot_exists(slot)

    def create_new_game(self, slot: int, base_seed: int = 1337) -> SaveData:
        data = self._slots.create_new_game(slot, base_seed=base_seed)
        data.vault.last_run_seed = base_seed
        self.save_slot(slot, data)
        return data

    def load_slot(self, slot: int) -> SaveData:
        return self._slots.load_slot(slot)

    def save_slot(self, slot: int, save_data: SaveData) -> None:
        self._slots.save_slot(slot, save_data)

    def delete_slot(self, slot: int) -> None:
        self._slots.delete_slot(slot)

    def rename_slot(self, slot: int, name: str) -> None:
        self._slots.rename_slot(slot, name)

    def last_slot(self) -> int | None:
        return self._slots.last_slot()
