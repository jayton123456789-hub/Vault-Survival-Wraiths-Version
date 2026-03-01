from __future__ import annotations

import json
from pathlib import Path

from .models import MATERIAL_ITEM_IDS, EquippedSlots, SAVE_VERSION, Citizen, SaveData, SettingsState, VaultState, default_materials
from .research import deploy_capacity, queue_capacity_bonus
from .rng import DeterministicRNG
from .save_system import migrate_save

DEFAULT_QUEUE_TARGET = 4
MAX_QUEUE_TARGET = 12
DEFAULT_ROSTER_TARGET = 1
MAX_ROSTER_TARGET = 8

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


def _pick_unique_name(rng: DeterministicRNG, used_names: set[str]) -> str:
    available = [name for name in NAME_POOL if name not in used_names]
    if available:
        return available[rng.next_int(0, len(available))]

    base = NAME_POOL[rng.next_int(0, len(NAME_POOL))]
    suffix = 2
    candidate = f"{base}-{suffix}"
    while candidate in used_names:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _pick_distinct_quirk(rng: DeterministicRNG, name: str, used_pairs: set[tuple[str, str]]) -> str:
    available = [quirk for quirk in QUIRK_POOL if (name, quirk) not in used_pairs]
    pool = available if available else QUIRK_POOL
    return pool[rng.next_int(0, len(pool))]


def _make_citizen(
    rng: DeterministicRNG,
    sequence: int,
    *,
    used_names: set[str] | None = None,
    used_pairs: set[tuple[str, str]] | None = None,
) -> Citizen:
    names = set() if used_names is None else used_names
    pairs = set() if used_pairs is None else used_pairs

    name = _pick_unique_name(rng, names)
    quirk = _pick_distinct_quirk(rng, name, pairs)
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
        "water_pouch": 2,
        "ration_pack": 2,
        "backpack_basic": 1,
        "armor_scrap": 1,
        "bike_rusty": 1,
        "lockpick_set": 1,
    }


def compute_queue_capacity(vault: VaultState) -> int:
    target = DEFAULT_QUEUE_TARGET + queue_capacity_bonus(vault)
    return max(DEFAULT_QUEUE_TARGET, min(MAX_QUEUE_TARGET, target))


def compute_roster_capacity(vault: VaultState) -> int:
    target = deploy_capacity(vault)
    return max(DEFAULT_ROSTER_TARGET, min(MAX_ROSTER_TARGET, target))


# Backwards-compatible aliases used by existing tests/scenes.
def citizen_queue_target(vault: VaultState) -> int:
    return compute_queue_capacity(vault)


def deploy_roster_target(vault: VaultState) -> int:
    return compute_roster_capacity(vault)


def _sync_capacity_fields(vault: VaultState) -> None:
    vault.citizen_queue_capacity = compute_queue_capacity(vault)
    vault.deploy_roster_capacity = compute_roster_capacity(vault)


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
        deploy_roster=[],
        citizen_reserve=[],
        current_citizen=None,
        active_deploy_citizen_id=None,
        fallen_citizens=[],
        citizen_queue_capacity=DEFAULT_QUEUE_TARGET,
        deploy_roster_capacity=DEFAULT_ROSTER_TARGET,
        milestones=set(),
        research_levels={},
        campaign_goal_unlocked=False,
        campaign_won=False,
        run_counter=0,
        last_run_seed=None,
        claw_rng_state=claw_seed.state,
        claw_rng_calls=claw_seed.calls,
        settings=SettingsState(base_seed=base_seed),
    )
    _sync_capacity_fields(vault)
    refill_citizen_queue(vault)
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
    _normalize_roster_state(hydrated.vault)
    _sync_capacity_fields(hydrated.vault)
    return hydrated


def save_save_data(state: SaveData, save_path: Path | str = "save.json") -> None:
    path = Path(save_path)
    state.save_version = SAVE_VERSION
    _normalize_roster_state(state.vault)
    _sync_capacity_fields(state.vault)
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


def _normalize_roster_state(vault: VaultState) -> None:
    _sync_capacity_fields(vault)
    seen_ids: set[str] = set()
    dedup_queue: list[Citizen] = []
    dedup_roster: list[Citizen] = []
    dedup_reserve: list[Citizen] = []
    dedup_fallen: list[Citizen] = []

    for citizen in vault.fallen_citizens:
        if citizen.id in seen_ids:
            continue
        citizen.status = "dead"
        seen_ids.add(citizen.id)
        dedup_fallen.append(citizen)

    for citizen in vault.deploy_roster:
        if citizen.status == "dead":
            if citizen.id not in seen_ids:
                seen_ids.add(citizen.id)
                dedup_fallen.append(citizen)
            continue
        if citizen.id in seen_ids:
            continue
        citizen.status = "ready"
        seen_ids.add(citizen.id)
        dedup_roster.append(citizen)
    for citizen in vault.citizen_queue:
        if citizen.id in seen_ids:
            continue
        citizen.status = "ready"
        seen_ids.add(citizen.id)
        dedup_queue.append(citizen)
    for citizen in vault.citizen_reserve:
        if citizen.id in seen_ids:
            continue
        if citizen.status == "dead":
            vault.fallen_citizens.append(citizen)
            continue
        citizen.status = "ready"
        seen_ids.add(citizen.id)
        dedup_reserve.append(citizen)

    vault.deploy_roster = dedup_roster
    vault.citizen_queue = dedup_queue
    vault.citizen_reserve = dedup_reserve
    vault.fallen_citizens = dedup_fallen

    if len(vault.deploy_roster) > vault.deploy_roster_capacity:
        overflow = vault.deploy_roster[vault.deploy_roster_capacity :]
        vault.deploy_roster = vault.deploy_roster[: vault.deploy_roster_capacity]
        vault.citizen_reserve.extend(overflow)
    if len(vault.citizen_queue) > vault.citizen_queue_capacity:
        overflow = vault.citizen_queue[vault.citizen_queue_capacity :]
        vault.citizen_queue = vault.citizen_queue[: vault.citizen_queue_capacity]
        vault.citizen_reserve.extend(overflow)

    if vault.active_deploy_citizen_id and not any(
        citizen.id == vault.active_deploy_citizen_id for citizen in vault.deploy_roster
    ):
        vault.active_deploy_citizen_id = None
    if vault.active_deploy_citizen_id is None and vault.current_citizen:
        if any(citizen.id == vault.current_citizen.id for citizen in vault.deploy_roster):
            vault.active_deploy_citizen_id = vault.current_citizen.id
    if vault.active_deploy_citizen_id is None and vault.deploy_roster:
        vault.active_deploy_citizen_id = vault.deploy_roster[0].id

    active = get_active_deploy_citizen(vault)
    vault.current_citizen = active


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


def _refill_from_reserve(vault: VaultState, target_size: int) -> None:
    while len(vault.citizen_queue) < target_size and vault.citizen_reserve:
        vault.citizen_queue.append(vault.citizen_reserve.pop(0))


def refill_citizen_queue(vault: VaultState, target_size: int | None = None) -> None:
    _sync_capacity_fields(vault)
    if target_size is None:
        target_size = vault.citizen_queue_capacity
    target_size = max(1, min(MAX_QUEUE_TARGET, int(target_size)))
    vault.citizen_queue_capacity = target_size

    if len(vault.citizen_queue) > target_size:
        overflow = vault.citizen_queue[target_size:]
        vault.citizen_queue = vault.citizen_queue[:target_size]
        vault.citizen_reserve.extend(overflow)

    _refill_from_reserve(vault, target_size)
    rng = _claw_rng(vault)
    sequence = vault.run_counter * 1000 + len(vault.citizen_queue) + len(vault.citizen_reserve) + len(vault.deploy_roster)

    visible_citizens = [*vault.citizen_queue, *vault.citizen_reserve, *vault.deploy_roster]
    if vault.current_citizen is not None:
        visible_citizens.append(vault.current_citizen)
    used_names = {citizen.name for citizen in visible_citizens}
    used_pairs = {(citizen.name, citizen.quirk) for citizen in visible_citizens}

    while len(vault.citizen_queue) < target_size:
        sequence += 1
        citizen = _make_citizen(rng, sequence=sequence, used_names=used_names, used_pairs=used_pairs)
        used_names.add(citizen.name)
        used_pairs.add((citizen.name, citizen.quirk))
        vault.citizen_queue.append(citizen)
    _save_claw_rng(vault, rng)


def _roster_is_full(vault: VaultState) -> bool:
    _sync_capacity_fields(vault)
    return len(vault.deploy_roster) >= vault.deploy_roster_capacity


def _activate_citizen(vault: VaultState, citizen: Citizen | None) -> None:
    if citizen is None:
        vault.active_deploy_citizen_id = None
        vault.current_citizen = None
    else:
        for candidate in vault.deploy_roster:
            candidate.status = "ready"
        citizen.status = "deployed"
        vault.active_deploy_citizen_id = citizen.id
        vault.current_citizen = citizen


def get_active_deploy_citizen(vault: VaultState) -> Citizen | None:
    if vault.active_deploy_citizen_id:
        for citizen in vault.deploy_roster:
            if citizen.id == vault.active_deploy_citizen_id and citizen.status != "dead":
                citizen.status = "deployed"
                vault.current_citizen = citizen
                return citizen
    if vault.current_citizen:
        for citizen in vault.deploy_roster:
            if citizen.id == vault.current_citizen.id and citizen.status != "dead":
                _activate_citizen(vault, citizen)
                return citizen
    if vault.deploy_roster:
        for citizen in vault.deploy_roster:
            if citizen.status != "dead":
                _activate_citizen(vault, citizen)
                return citizen
    _activate_citizen(vault, None)
    return None


def select_roster_citizen_for_deploy(vault: VaultState, citizen_id: str) -> Citizen:
    for citizen in vault.deploy_roster:
        if citizen.id == citizen_id:
            _activate_citizen(vault, citizen)
            return citizen
    raise ValueError(f"Citizen '{citizen_id}' not found in deploy roster.")


def _append_to_roster(vault: VaultState, citizen: Citizen) -> bool:
    if _roster_is_full(vault):
        return False
    citizen.status = "ready"
    vault.deploy_roster.append(citizen)
    _activate_citizen(vault, citizen)
    return True


def transfer_selected_citizen_to_roster(vault: VaultState, citizen_id: str) -> Citizen:
    if _roster_is_full(vault):
        raise ValueError("Deploy roster is full.")
    for idx, candidate in enumerate(vault.citizen_queue):
        if candidate.id == citizen_id:
            selected = vault.citizen_queue.pop(idx)
            if not _append_to_roster(vault, selected):
                vault.citizen_queue.insert(idx, selected)
                raise ValueError("Deploy roster is full.")
            refill_citizen_queue(vault)
            return selected
    raise ValueError(f"Citizen '{citizen_id}' not found in queue.")


def transfer_claw_pick_to_roster(
    vault: VaultState,
    preview_count: int = 5,
    expected_citizen_id: str | None = None,
) -> Citizen:
    if _roster_is_full(vault):
        raise ValueError("Deploy roster is full.")
    if not vault.citizen_queue:
        refill_citizen_queue(vault)
    if not vault.citizen_queue:
        raise ValueError("Citizen queue is empty.")

    rng = _claw_rng(vault)
    window = min(preview_count, len(vault.citizen_queue))
    index = rng.next_int(0, max(1, window))
    if expected_citizen_id:
        for candidate_idx in range(window):
            if vault.citizen_queue[candidate_idx].id == expected_citizen_id:
                index = candidate_idx
                break
    selected = vault.citizen_queue.pop(index)
    if not _append_to_roster(vault, selected):
        vault.citizen_queue.insert(index, selected)
        raise ValueError("Deploy roster is full.")
    _save_claw_rng(vault, rng)
    refill_citizen_queue(vault)
    return selected


def remove_citizen_from_roster(vault: VaultState, citizen_id: str) -> Citizen | None:
    for idx, citizen in enumerate(vault.deploy_roster):
        if citizen.id == citizen_id:
            removed = vault.deploy_roster.pop(idx)
            if vault.active_deploy_citizen_id == citizen_id:
                vault.active_deploy_citizen_id = None
            return removed
    return None


def on_run_finished(vault: VaultState, result: str, citizen_id: str | None = None) -> None:
    _sync_capacity_fields(vault)
    active = get_active_deploy_citizen(vault)
    target_id = citizen_id or (active.id if active else None) or vault.active_deploy_citizen_id
    if result == "death" and target_id:
        removed = remove_citizen_from_roster(vault, target_id)
        if removed and removed.id == target_id:
            removed.status = "dead"
            removed.death_count += 1
            vault.fallen_citizens.append(removed)
            vault.current_citizen = None
    elif result == "retreat":
        if target_id and not any(c.id == target_id for c in vault.deploy_roster) and vault.current_citizen:
            if not _roster_is_full(vault):
                vault.current_citizen.status = "ready"
                vault.deploy_roster.append(vault.current_citizen)
            else:
                vault.current_citizen.status = "ready"
                vault.citizen_reserve.append(vault.current_citizen)
        active = get_active_deploy_citizen(vault)
        if active:
            active.status = "ready"
            active.completed_runs += 1
    elif result == "extracted":
        if target_id and not any(c.id == target_id for c in vault.deploy_roster) and vault.current_citizen:
            if not _roster_is_full(vault):
                vault.current_citizen.status = "ready"
                vault.deploy_roster.append(vault.current_citizen)
            else:
                vault.current_citizen.status = "ready"
                vault.citizen_reserve.append(vault.current_citizen)
        active = get_active_deploy_citizen(vault)
        if active:
            active.status = "ready"
            active.completed_runs += 1

    if vault.active_deploy_citizen_id is None:
        get_active_deploy_citizen(vault)
    refill_citizen_queue(vault)


# Backwards-compatible wrappers (kept for existing callsites/tests).
def draft_citizen_from_claw(vault: VaultState, preview_count: int = 5) -> Citizen:
    return transfer_claw_pick_to_roster(vault, preview_count=preview_count)


def draft_selected_citizen(vault: VaultState, citizen_id: str) -> Citizen:
    return transfer_selected_citizen_to_roster(vault, citizen_id=citizen_id)
