from __future__ import annotations

import json
from pathlib import Path

from .models import MATERIAL_ITEM_IDS, EquippedSlots, SAVE_VERSION, Citizen, SaveData, SettingsState, VaultState, default_materials
from .rng import DeterministicRNG
from .save_system import migrate_save

DEFAULT_QUEUE_TARGET = 12

NAME_POOL = [
    "Ari",
    "Mina",
    "Jax",
    "Kira",
    "Theo",
    "Rook",
    "Vale",
    "Iris",
    "Soren",
    "Nox",
    "Pax",
    "Rey",
    "Dax",
    "Nova",
    "Lio",
    "Rune",
]

QUIRK_POOL = [
    "Always hums old radio jingles",
    "Refuses to waste batteries",
    "Collects bottle caps",
    "Sleeps lightly",
    "Talks to stray dogs",
    "Never forgets routes",
    "Counts every ration",
    "Trusts weather instincts",
    "Hates enclosed spaces",
    "Swears by lucky charms",
]


def _claw_rng(vault: VaultState) -> DeterministicRNG:
    return DeterministicRNG(seed=vault.settings.base_seed, state=vault.claw_rng_state, calls=vault.claw_rng_calls)


def _save_claw_rng(vault: VaultState, rng: DeterministicRNG) -> None:
    vault.claw_rng_state = rng.state
    vault.claw_rng_calls = rng.calls


def _make_citizen(rng: DeterministicRNG, sequence: int) -> Citizen:
    name = NAME_POOL[rng.next_int(0, len(NAME_POOL))]
    quirk = QUIRK_POOL[rng.next_int(0, len(QUIRK_POOL))]
    cid = f"cit_{sequence:04d}_{rng.state:08x}"
    kit = {
        "water_pouch": 1,
        "ration_pack": 1,
    }
    if rng.next_float() < 0.4:
        kit["scrap"] = 1 + rng.next_int(0, 3)
    if rng.next_float() < 0.25:
        kit["cloth"] = 1 + rng.next_int(0, 2)
    if "batteries" in quirk.lower() and rng.next_float() < 0.55:
        kit["battery_bank"] = 1
    if "routes" in quirk.lower() and rng.next_float() < 0.45:
        kit["lockpick_set"] = 1
    return Citizen(
        id=cid,
        name=name,
        quirk=quirk,
        kit=kit,
        loadout=EquippedSlots(),
        kit_seed=rng.state,
    )


def _default_storage() -> dict[str, int]:
    return {
        "water_pouch": 4,
        "ration_pack": 4,
        "backpack_basic": 1,
        "armor_scrap": 1,
        "bike_rusty": 1,
        "filter_mask": 1,
        "lockpick_set": 1,
        "radio_parts": 1,
        "badge_police": 1,
        "med_armband": 1,
    }


def create_default_vault_state(base_seed: int = 1337) -> VaultState:
    claw_seed = DeterministicRNG.from_seed(f"{base_seed}:claw")
    vault = VaultState(
        materials={"scrap": 22, "cloth": 16, "plastic": 14, "metal": 12},
        storage=_default_storage(),
        blueprints={"field_pack_recipe", "patchwork_armor_recipe"},
        upgrades={"drone_bay_level": 0},
        tav=0,
        vaultLevel=1,
        citizen_queue=[],
        current_citizen=None,
        milestones=set(),
        run_counter=0,
        last_run_seed=None,
        claw_rng_state=claw_seed.state,
        claw_rng_calls=claw_seed.calls,
        settings=SettingsState(base_seed=base_seed),
    )
    refill_citizen_queue(vault, target_size=DEFAULT_QUEUE_TARGET)
    return vault


def create_default_save_data(base_seed: int = 1337) -> SaveData:
    return SaveData(save_version=SAVE_VERSION, vault=create_default_vault_state(base_seed=base_seed))


def load_save_data(save_path: Path | str = "save.json", base_seed: int = 1337) -> SaveData:
    path = Path(save_path)
    if not path.exists():
        return create_default_save_data(base_seed=base_seed)
    data = json.loads(path.read_text(encoding="utf-8"))
    payload = migrate_save(data)
    hydrated = SaveData.model_validate(payload)
    hydrated.save_version = SAVE_VERSION
    _migrate_materials(hydrated.vault)
    return hydrated


def save_save_data(state: SaveData, save_path: Path | str = "save.json") -> None:
    path = Path(save_path)
    state.save_version = SAVE_VERSION
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")


def _migrate_materials(vault: VaultState) -> None:
    if not vault.materials:
        vault.materials = default_materials()
    for material_id in MATERIAL_ITEM_IDS:
        qty = int(vault.storage.pop(material_id, 0))
        if qty > 0:
            vault.materials[material_id] = int(vault.materials.get(material_id, 0)) + qty
        else:
            vault.materials.setdefault(material_id, 0)


def store_item(vault: VaultState, item_id: str, qty: int = 1) -> None:
    if qty <= 0:
        return
    if item_id in MATERIAL_ITEM_IDS:
        vault.materials[item_id] = int(vault.materials.get(item_id, 0)) + qty
        return
    vault.storage[item_id] = int(vault.storage.get(item_id, 0)) + qty


def take_item(vault: VaultState, item_id: str, qty: int = 1) -> bool:
    if qty <= 0:
        return True
    if item_id in MATERIAL_ITEM_IDS:
        current = int(vault.materials.get(item_id, 0))
        if current < qty:
            return False
        vault.materials[item_id] = current - qty
        return True

    current = int(vault.storage.get(item_id, 0))
    if current < qty:
        return False
    remaining = current - qty
    if remaining <= 0:
        vault.storage.pop(item_id, None)
    else:
        vault.storage[item_id] = remaining
    return True


def storage_used(vault: VaultState) -> int:
    return sum(max(0, int(qty)) for qty in vault.storage.values())


def refill_citizen_queue(vault: VaultState, target_size: int = DEFAULT_QUEUE_TARGET) -> None:
    rng = _claw_rng(vault)
    sequence = vault.run_counter * 1000 + len(vault.citizen_queue)
    while len(vault.citizen_queue) < target_size:
        sequence += 1
        vault.citizen_queue.append(_make_citizen(rng, sequence=sequence))
    _save_claw_rng(vault, rng)


def draft_citizen_from_claw(vault: VaultState, preview_count: int = 5) -> Citizen:
    if not vault.citizen_queue:
        refill_citizen_queue(vault, target_size=DEFAULT_QUEUE_TARGET)

    rng = _claw_rng(vault)
    window = min(preview_count, len(vault.citizen_queue))
    index = rng.next_int(0, max(1, window))
    selected = vault.citizen_queue.pop(index)
    vault.current_citizen = selected
    _save_claw_rng(vault, rng)
    refill_citizen_queue(vault, target_size=DEFAULT_QUEUE_TARGET)
    return selected


def draft_selected_citizen(vault: VaultState, citizen_id: str) -> Citizen:
    for idx, candidate in enumerate(vault.citizen_queue):
        if candidate.id == citizen_id:
            selected = vault.citizen_queue.pop(idx)
            vault.current_citizen = selected
            refill_citizen_queue(vault, target_size=DEFAULT_QUEUE_TARGET)
            return selected
    raise ValueError(f"Citizen '{citizen_id}' not found in queue.")
