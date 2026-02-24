from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bit_life_survival.core.models import SaveData
from bit_life_survival.core.persistence import create_default_save_data, load_save_data, save_save_data


@dataclass(slots=True)
class SlotSummary:
    slot: int
    occupied: bool
    slot_name: str
    vault_level: int = 1
    tav: int = 0
    drone_bay_level: int = 0
    run_count: int = 0
    seed_preview: str = "-"
    last_distance: float = 0.0
    last_time: int = 0
    last_played: str | None = None


class SaveService:
    def __init__(self, saves_dir: Path, slot_count: int = 3) -> None:
        self.saves_dir = saves_dir
        self.slot_count = max(3, min(6, int(slot_count)))
        self.slot_ids = tuple(range(1, self.slot_count + 1))
        self.meta_path = self.saves_dir / "meta.json"
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        if not self.meta_path.exists():
            self._write_meta({"last_slot": None, "slot_count": self.slot_count, "slots": {}})

    def _slot_path(self, slot: int) -> Path:
        return self.saves_dir / f"slot{slot}.json"

    def _default_slot_meta(self, slot: int) -> dict[str, Any]:
        return {
            "slot_name": f"Slot {slot}",
            "last_played": None,
            "run_count": 0,
            "seed_preview": "-",
            "vault_level": 1,
            "tav": 0,
        }

    def _read_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            return {"last_slot": None, "slot_count": self.slot_count, "slots": {}}
        try:
            payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("last_slot", None)
        payload["slot_count"] = max(3, min(6, int(payload.get("slot_count", self.slot_count))))
        payload.setdefault("slots", {})
        return payload

    def _write_meta(self, payload: dict[str, Any]) -> None:
        self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _touch_meta_slot(self, slot: int, save_data: SaveData | None = None) -> None:
        meta = self._read_meta()
        slots = meta.setdefault("slots", {})
        slot_key = str(slot)
        entry = slots.setdefault(slot_key, self._default_slot_meta(slot))
        entry["last_played"] = datetime.now(timezone.utc).isoformat()
        if save_data is not None:
            vault = save_data.vault
            entry["vault_level"] = int(vault.vault_level)
            entry["tav"] = int(vault.tav)
            entry["run_count"] = int(vault.run_counter)
            entry["seed_preview"] = str(vault.last_run_seed if vault.last_run_seed is not None else vault.settings.base_seed)
            entry.setdefault("slot_name", f"Slot {slot}")
        meta["last_slot"] = slot
        self._write_meta(meta)

    def list_slots(self) -> list[SlotSummary]:
        meta = self._read_meta()
        summaries: list[SlotSummary] = []
        for slot in self.slot_ids:
            path = self._slot_path(slot)
            slot_meta = meta.get("slots", {}).get(str(slot), self._default_slot_meta(slot))
            if not path.exists():
                summaries.append(
                    SlotSummary(
                        slot=slot,
                        occupied=False,
                        slot_name=str(slot_meta.get("slot_name", f"Slot {slot}")),
                        run_count=int(slot_meta.get("run_count", 0)),
                        seed_preview=str(slot_meta.get("seed_preview", "-")),
                        last_played=slot_meta.get("last_played"),
                    )
                )
                continue
            data = load_save_data(path)
            vault = data.vault
            summaries.append(
                SlotSummary(
                    slot=slot,
                    occupied=True,
                    slot_name=str(slot_meta.get("slot_name", f"Slot {slot}")),
                    vault_level=vault.vault_level,
                    tav=vault.tav,
                    drone_bay_level=int(vault.upgrades.get("drone_bay_level", 0)),
                    run_count=int(vault.run_counter),
                    seed_preview=str(vault.last_run_seed if vault.last_run_seed is not None else vault.settings.base_seed),
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
        data.vault.last_run_seed = base_seed
        self.save_slot(slot, data)
        return data

    def load_slot(self, slot: int) -> SaveData:
        data = load_save_data(self._slot_path(slot))
        self._touch_meta_slot(slot, save_data=data)
        return data

    def save_slot(self, slot: int, save_data: SaveData) -> None:
        save_save_data(save_data, self._slot_path(slot))
        self._touch_meta_slot(slot, save_data=save_data)

    def delete_slot(self, slot: int) -> None:
        self._slot_path(slot).unlink(missing_ok=True)
        meta = self._read_meta()
        meta.get("slots", {}).pop(str(slot), None)
        if meta.get("last_slot") == slot:
            meta["last_slot"] = None
        self._write_meta(meta)

    def rename_slot(self, slot: int, name: str) -> None:
        clean = name.strip()
        if not clean:
            raise ValueError("Slot name cannot be empty.")
        meta = self._read_meta()
        slots = meta.setdefault("slots", {})
        entry = slots.setdefault(str(slot), self._default_slot_meta(slot))
        entry["slot_name"] = clean[:32]
        self._write_meta(meta)

    def last_slot(self) -> int | None:
        value = self._read_meta().get("last_slot")
        if isinstance(value, int) and value in self.slot_ids:
            return value
        return None
