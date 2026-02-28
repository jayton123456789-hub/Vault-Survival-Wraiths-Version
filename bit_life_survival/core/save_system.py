from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import MATERIAL_ITEM_IDS, RUNNER_EQUIP_SLOTS, SAVE_VERSION, SaveData

DEFAULT_SLOT_COUNT = 3
MIN_SLOT_COUNT = 3
MAX_SLOT_COUNT = 5


def normalize_slot_count(slot_count: int) -> int:
    return max(MIN_SLOT_COUNT, min(MAX_SLOT_COUNT, int(slot_count)))


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
    drafted_citizen: str | None = None


def _coerce_dict(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {} if default is None else dict(default)


def _default_loadout_payload() -> dict[str, Any]:
    return {slot: None for slot in RUNNER_EQUIP_SLOTS}


def _queue_capacity_formula(vault: dict[str, Any]) -> int:
    vault_level = int(vault.get("vaultLevel", 1) or 1)
    tav = int(vault.get("tav", 0) or 0)
    upgrades = _coerce_dict(vault.get("upgrades"))
    drone_level = int(upgrades.get("drone_bay_level", 0) or 0)
    value = 4 + max(0, vault_level - 1) + min(4, tav // 50) + min(2, drone_level // 2)
    return max(4, min(12, value))


def _roster_capacity_formula(vault: dict[str, Any]) -> int:
    vault_level = int(vault.get("vaultLevel", 1) or 1)
    tav = int(vault.get("tav", 0) or 0)
    upgrades = _coerce_dict(vault.get("upgrades"))
    drone_level = int(upgrades.get("drone_bay_level", 0) or 0)
    value = 1 + max(0, vault_level - 1) + min(3, tav // 60) + min(2, drone_level)
    return max(1, min(8, value))


def _migrate_legacy_injuries(payload: dict[str, Any]) -> None:
    run_state = _coerce_dict(payload.get("run_state"))
    if not run_state:
        return
    injury_value = float(run_state.get("injury", 0.0) or 0.0)
    injuries = _coerce_dict(run_state.get("injuries"), default={"torso": 0.0})
    if injury_value > 0 and sum(float(v or 0.0) for v in injuries.values()) <= 0:
        injuries["torso"] = injury_value
    run_state["injuries"] = injuries
    run_state["injury"] = max(injury_value, sum(float(v or 0.0) for v in injuries.values()))
    payload["run_state"] = run_state


def _migrate_legacy_materials(vault: dict[str, Any]) -> None:
    storage = _coerce_dict(vault.get("storage"))
    materials = _coerce_dict(vault.get("materials"))
    for material_id in MATERIAL_ITEM_IDS:
        qty = int(storage.pop(material_id, 0) or 0)
        if qty > 0:
            materials[material_id] = int(materials.get(material_id, 0) or 0) + qty
        else:
            materials.setdefault(material_id, 0)
    vault["storage"] = storage
    vault["materials"] = materials


def _migrate_legacy_citizens(vault: dict[str, Any]) -> None:
    def hydrate_citizen(raw: Any) -> dict[str, Any]:
        citizen = _coerce_dict(raw)
        citizen.setdefault("id", "cit_unknown")
        citizen.setdefault("name", "Unknown")
        citizen.setdefault("quirk", "No profile")
        citizen["kit"] = _coerce_dict(citizen.get("kit"))
        citizen["loadout"] = _coerce_dict(citizen.get("loadout"), default=_default_loadout_payload())
        for slot in RUNNER_EQUIP_SLOTS:
            citizen["loadout"].setdefault(slot, None)
        return citizen

    queue = vault.get("citizen_queue")
    if isinstance(queue, list):
        vault["citizen_queue"] = [hydrate_citizen(entry) for entry in queue]
    else:
        vault["citizen_queue"] = []

    deploy_roster = vault.get("deploy_roster")
    if isinstance(deploy_roster, list):
        vault["deploy_roster"] = [hydrate_citizen(entry) for entry in deploy_roster]
    else:
        vault["deploy_roster"] = []

    reserve = vault.get("citizen_reserve")
    if isinstance(reserve, list):
        vault["citizen_reserve"] = [hydrate_citizen(entry) for entry in reserve]
    else:
        vault["citizen_reserve"] = []

    current = vault.get("current_citizen")
    if current is not None:
        vault["current_citizen"] = hydrate_citizen(current)


def _migrate_v2_to_v3(payload: dict[str, Any]) -> dict[str, Any]:
    vault = _coerce_dict(payload.get("vault"))
    _migrate_legacy_materials(vault)
    _migrate_legacy_citizens(vault)

    queue = list(vault.get("citizen_queue", []))
    roster = list(vault.get("deploy_roster", []))
    reserve = list(vault.get("citizen_reserve", []))

    current = vault.get("current_citizen")
    if current:
        current_id = str(current.get("id", ""))
        if current_id and not any(c.get("id") == current_id for c in roster):
            roster.insert(0, current)
    active_id = vault.get("active_deploy_citizen_id")
    if not active_id and current:
        active_id = current.get("id")

    queue_cap = _queue_capacity_formula(vault)
    roster_cap = _roster_capacity_formula(vault)

    if len(roster) > roster_cap:
        reserve.extend(roster[roster_cap:])
        roster = roster[:roster_cap]
    if len(queue) > queue_cap:
        reserve.extend(queue[queue_cap:])
        queue = queue[:queue_cap]

    roster_ids = {citizen.get("id") for citizen in roster}
    queue = [citizen for citizen in queue if citizen.get("id") not in roster_ids]
    reserve = [citizen for citizen in reserve if citizen.get("id") not in roster_ids]

    if active_id and active_id not in roster_ids:
        active_id = roster[0].get("id") if roster else None
    if not active_id and roster:
        active_id = roster[0].get("id")

    vault["citizen_queue"] = queue
    vault["deploy_roster"] = roster
    vault["citizen_reserve"] = reserve
    vault["active_deploy_citizen_id"] = active_id
    vault["citizen_queue_capacity"] = queue_cap
    vault["deploy_roster_capacity"] = roster_cap
    vault["current_citizen"] = next((citizen for citizen in roster if citizen.get("id") == active_id), None)
    payload["vault"] = vault
    payload["save_version"] = 3
    return payload


def _migrate_v3_to_v4(payload: dict[str, Any]) -> dict[str, Any]:
    vault = _coerce_dict(payload.get("vault"))
    settings = _coerce_dict(vault.get("settings"))
    settings.setdefault("theme_preset", "ember")
    try:
        font_scale = float(settings.get("font_scale", 1.0))
    except (TypeError, ValueError):
        font_scale = 1.0
    settings["font_scale"] = max(0.75, min(1.6, font_scale))
    settings["show_tooltips"] = bool(settings.get("show_tooltips", True))
    vault["settings"] = settings
    payload["vault"] = vault
    payload["save_version"] = 4
    return payload


def _migrate_v0_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    if "vault" not in payload:
        payload = {"vault": payload}
    vault = _coerce_dict(payload.get("vault"))
    _migrate_legacy_materials(vault)
    _migrate_legacy_citizens(vault)
    payload["vault"] = vault
    _migrate_legacy_injuries(payload)
    payload["save_version"] = 1
    return payload


def _migrate_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    vault = _coerce_dict(payload.get("vault"))
    _migrate_legacy_materials(vault)
    _migrate_legacy_citizens(vault)
    payload["vault"] = vault
    payload["save_version"] = 2
    return payload


MIGRATION_STEPS: dict[int, Any] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
}


def migrate_save(payload: Any) -> dict[str, Any]:
    state = _coerce_dict(payload)
    if "vault" not in state:
        state = {"vault": state}

    version_raw = state.get("save_version")
    try:
        version = int(version_raw) if version_raw is not None else 0
    except (TypeError, ValueError):
        version = 0
    if version < 0:
        version = 0
    if version > SAVE_VERSION:
        version = SAVE_VERSION

    while version < SAVE_VERSION:
        step = MIGRATION_STEPS.get(version)
        if step is None:
            raise ValueError(f"No migration step defined from version {version}.")
        state = step(state)
        version = int(state.get("save_version", version + 1))
    state["save_version"] = SAVE_VERSION
    return state


class SlotStorage:
    def __init__(self, saves_dir: Path, slot_count: int = DEFAULT_SLOT_COUNT) -> None:
        self.saves_dir = saves_dir
        self.slot_count = normalize_slot_count(slot_count)
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
            "last_distance": 0.0,
            "last_time": 0,
            "drafted_citizen": None,
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
        payload["slot_count"] = normalize_slot_count(payload.get("slot_count", self.slot_count))
        payload.setdefault("slots", {})
        return payload

    def _write_meta(self, payload: dict[str, Any]) -> None:
        self.meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def slot_exists(self, slot: int) -> bool:
        return self._slot_path(slot).exists()

    def load_slot(self, slot: int, base_seed: int = 1337) -> SaveData:
        from .persistence import create_default_save_data

        path = self._slot_path(slot)
        if not path.exists():
            data = create_default_save_data(base_seed=base_seed)
            data.save_version = SAVE_VERSION
            self.save_slot(slot, data)
            return data
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = SaveData.model_validate(migrate_save(payload))
        self._touch_meta_slot(slot, save_data=data)
        return data

    def save_slot(self, slot: int, save_data: SaveData) -> None:
        save_data.save_version = SAVE_VERSION
        path = self._slot_path(slot)
        path.write_text(json.dumps(save_data.model_dump(mode="json"), indent=2), encoding="utf-8")
        self._touch_meta_slot(slot, save_data=save_data)

    def create_new_game(self, slot: int, base_seed: int = 1337) -> SaveData:
        from .persistence import create_default_save_data

        data = create_default_save_data(base_seed=base_seed)
        data.save_version = SAVE_VERSION
        self.save_slot(slot, data)
        return data

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
        entry = meta.setdefault("slots", {}).setdefault(str(slot), self._default_slot_meta(slot))
        entry["slot_name"] = clean[:32]
        self._write_meta(meta)

    def last_slot(self) -> int | None:
        value = self._read_meta().get("last_slot")
        if isinstance(value, int) and value in self.slot_ids:
            return value
        return None

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
            entry["last_distance"] = float(getattr(vault, "last_run_distance", 0.0) or 0.0)
            entry["last_time"] = int(getattr(vault, "last_run_time", 0) or 0)
            drafted = None
            if getattr(vault, "active_deploy_citizen_id", None):
                drafted = next(
                    (citizen.name for citizen in getattr(vault, "deploy_roster", []) if citizen.id == vault.active_deploy_citizen_id),
                    None,
                )
            entry["drafted_citizen"] = drafted or (vault.current_citizen.name if vault.current_citizen else None)
            entry.setdefault("slot_name", f"Slot {slot}")
        meta["last_slot"] = slot
        self._write_meta(meta)

    def list_slots(self) -> list[SlotSummary]:
        summaries: list[SlotSummary] = []
        meta = self._read_meta()
        slots_meta = _coerce_dict(meta.get("slots"))
        for slot in self.slot_ids:
            slot_meta = _coerce_dict(slots_meta.get(str(slot)), default=self._default_slot_meta(slot))
            path = self._slot_path(slot)
            if not path.exists():
                summaries.append(
                    SlotSummary(
                        slot=slot,
                        occupied=False,
                        slot_name=str(slot_meta.get("slot_name", f"Slot {slot}")),
                        run_count=int(slot_meta.get("run_count", 0)),
                        seed_preview=str(slot_meta.get("seed_preview", "-")),
                        last_distance=float(slot_meta.get("last_distance", 0.0) or 0.0),
                        last_time=int(slot_meta.get("last_time", 0) or 0),
                        last_played=slot_meta.get("last_played"),
                        drafted_citizen=slot_meta.get("drafted_citizen"),
                    )
                )
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                data = SaveData.model_validate(migrate_save(payload))
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
                        drafted_citizen=next(
                            (
                                citizen.name
                                for citizen in getattr(vault, "deploy_roster", [])
                                if citizen.id == getattr(vault, "active_deploy_citizen_id", None)
                            ),
                            vault.current_citizen.name if vault.current_citizen else slot_meta.get("drafted_citizen"),
                        ),
                    )
                )
            except Exception:
                summaries.append(
                    SlotSummary(
                        slot=slot,
                        occupied=False,
                        slot_name=str(slot_meta.get("slot_name", f"Slot {slot}")),
                        last_played=slot_meta.get("last_played"),
                    )
                )
        return summaries
