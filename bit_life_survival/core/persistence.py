from __future__ import annotations

import json
from pathlib import Path

from .models import Citizen, SaveData, SettingsState, VaultState
from .rng import DeterministicRNG

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
    return Citizen(id=cid, name=name, quirk=quirk)


def _default_storage() -> dict[str, int]:
    return {
        "scrap": 22,
        "cloth": 16,
        "plastic": 14,
        "metal": 12,
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
    return SaveData(vault=create_default_vault_state(base_seed=base_seed))


def load_save_data(save_path: Path | str = "save.json", base_seed: int = 1337) -> SaveData:
    path = Path(save_path)
    if not path.exists():
        return create_default_save_data(base_seed=base_seed)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "vault" in data:
        return SaveData.model_validate(data)
    # Backward compatibility with older save format containing only vault object.
    return SaveData(vault=VaultState.model_validate(data))


def save_save_data(state: SaveData, save_path: Path | str = "save.json") -> None:
    path = Path(save_path)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")


def store_item(vault: VaultState, item_id: str, qty: int = 1) -> None:
    if qty <= 0:
        return
    vault.storage[item_id] = vault.storage.get(item_id, 0) + qty


def take_item(vault: VaultState, item_id: str, qty: int = 1) -> bool:
    if qty <= 0:
        return True
    current = vault.storage.get(item_id, 0)
    if current < qty:
        return False
    remaining = current - qty
    if remaining <= 0:
        vault.storage.pop(item_id, None)
    else:
        vault.storage[item_id] = remaining
    return True


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
