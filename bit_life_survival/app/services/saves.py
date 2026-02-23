from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bit_life_survival.core.models import SaveData
from bit_life_survival.core.persistence import create_default_save_data, load_save_data, save_save_data


SLOT_IDS = (1, 2, 3)


@dataclass(slots=True)
class SlotSummary:
    slot: int
    occupied: bool
    vault_level: int = 1
    tav: int = 0
    drone_bay_level: int = 0
    last_distance: float = 0.0
    last_time: int = 0
    last_played: str | None = None


class SaveService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.saves_dir = repo_root / "saves"
        self.meta_path = self.saves_dir / "meta.json"
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        if not self.meta_path.exists():
            self._write_meta({"last_slot": None, "slots": {}})

    def _slot_path(self, slot: int) -> Path:
        return self.saves_dir / f"slot{slot}.json"

    def _read_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            return {"last_slot": None, "slots": {}}
        try:
            payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("last_slot", None)
        payload.setdefault("slots", {})
        return payload

    def _write_meta(self, payload: dict[str, Any]) -> None:
        self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _touch_meta_slot(self, slot: int) -> None:
        meta = self._read_meta()
        slots = meta.setdefault("slots", {})
        slot_key = str(slot)
        entry = slots.setdefault(slot_key, {})
        entry["last_played"] = datetime.now(timezone.utc).isoformat()
        meta["last_slot"] = slot
        self._write_meta(meta)

    def list_slots(self) -> list[SlotSummary]:
        meta = self._read_meta()
        summaries: list[SlotSummary] = []
        for slot in SLOT_IDS:
            path = self._slot_path(slot)
            slot_meta = meta.get("slots", {}).get(str(slot), {})
            if not path.exists():
                summaries.append(SlotSummary(slot=slot, occupied=False, last_played=slot_meta.get("last_played")))
                continue
            data = load_save_data(path)
            vault = data.vault
            summaries.append(
                SlotSummary(
                    slot=slot,
                    occupied=True,
                    vault_level=vault.vault_level,
                    tav=vault.tav,
                    drone_bay_level=int(vault.upgrades.get("drone_bay_level", 0)),
                    last_distance=float(getattr(vault, "last_run_distance", 0.0) or 0.0),
                    last_time=int(getattr(vault, "last_run_time", 0) or 0),
                    last_played=slot_meta.get("last_played"),
                )
            )
        return summaries

    def slot_exists(self, slot: int) -> bool:
        return self._slot_path(slot).exists()

    def create_new_game(self, slot: int, base_seed: int = 1337) -> SaveData:
        data = create_default_save_data(base_seed=base_seed)
        self.save_slot(slot, data)
        return data

    def load_slot(self, slot: int) -> SaveData:
        data = load_save_data(self._slot_path(slot))
        self._touch_meta_slot(slot)
        return data

    def save_slot(self, slot: int, save_data: SaveData) -> None:
        save_save_data(save_data, self._slot_path(slot))
        self._touch_meta_slot(slot)

    def last_slot(self) -> int | None:
        value = self._read_meta().get("last_slot")
        if isinstance(value, int) and value in SLOT_IDS:
            return value
        return None
