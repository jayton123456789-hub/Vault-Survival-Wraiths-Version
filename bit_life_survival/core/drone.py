from __future__ import annotations

from dataclasses import dataclass

from .loader import ContentBundle
from .models import GameState, ItemRarity, VaultState
from .persistence import store_item
from .rng import DeterministicRNG


@dataclass(slots=True)
class DroneRecoveryReport:
    status: str
    recovery_chance: float
    recovered: dict[str, int]
    lost: dict[str, int]
    tav_gain: int
    milestone_awards: list[str]
    distance_tav: int
    rare_bonus: int
    milestone_bonus: int
    penalty_adjustment: int


def _pack_recovery_bonus(pack_rarity: ItemRarity | None) -> float:
    if pack_rarity == "legendary":
        return 0.16
    if pack_rarity == "rare":
        return 0.1
    if pack_rarity == "uncommon":
        return 0.06
    if pack_rarity == "common":
        return 0.03
    return 0.0


def _recovery_status(total: int, recovered: int) -> str:
    if total <= 0:
        return "full"
    ratio = recovered / total
    if ratio >= 0.85:
        return "full"
    if ratio >= 0.5:
        return "partial"
    if ratio >= 0.2:
        return "damaged"
    return "lost"


def _distance_tav(distance: float) -> int:
    if distance < 15:
        return 2
    if distance < 30:
        return 5
    if distance < 60:
        return 10
    if distance < 100:
        return 16
    if distance < 150:
        return 24
    return 35


def _milestone_bonus(vault: VaultState, distance: float) -> tuple[int, list[str]]:
    thresholds = [25, 50, 75, 100, 150]
    gained = 0
    awards: list[str] = []
    for threshold in thresholds:
        key = f"distance_{threshold}"
        if distance >= threshold and key not in vault.milestones:
            vault.milestones.add(key)
            gained += 5
            awards.append(key)
    return gained, awards


def _drone_rng(state: GameState) -> DeterministicRNG:
    mixed = (state.rng_state ^ 0xA5A5A5A5) & 0xFFFFFFFF
    if mixed == 0:
        mixed = 0x9E3779B9
    return DeterministicRNG(seed=f"{state.seed}:drone", state=mixed, calls=state.rng_calls)


def _collect_recoverable_items(state: GameState) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item_id, qty in state.inventory.items():
        if qty > 0:
            merged[item_id] = merged.get(item_id, 0) + qty
    for item_id in state.equipped.as_values():
        merged[item_id] = merged.get(item_id, 0) + 1
    return merged


def _rare_item_bonus(recovered: dict[str, int], content: ContentBundle) -> int:
    bonus = 0
    for item_id, qty in recovered.items():
        item = content.item_by_id.get(item_id)
        if item is None:
            continue
        if item.rarity == "rare":
            bonus += qty * 2
        elif item.rarity == "legendary":
            bonus += qty * 5
    return bonus


def run_drone_recovery(vault: VaultState, state: GameState, content: ContentBundle) -> DroneRecoveryReport:
    drone_level = int(vault.upgrades.get("drone_bay_level", 0))
    pack_item = content.item_by_id.get(state.equipped.pack) if state.equipped.pack else None
    pack_bonus = _pack_recovery_bonus(pack_item.rarity if pack_item else None)

    penalties = 0.0
    for flag in state.death_flags:
        if flag in {"burned", "submerged", "fell", "toxic_exposure"}:
            penalties += 0.12
        elif flag == "retreated_early":
            penalties += 0.08

    recovery_chance = max(0.05, min(0.95, 0.35 + (0.12 * drone_level) + pack_bonus - penalties))

    recoverable = _collect_recoverable_items(state)
    rng = _drone_rng(state)
    recovered: dict[str, int] = {}
    lost: dict[str, int] = {}

    for item_id, qty in recoverable.items():
        recovered_qty = 0
        for _ in range(qty):
            if rng.next_float() <= recovery_chance:
                recovered_qty += 1
        if recovered_qty > 0:
            recovered[item_id] = recovered_qty
            store_item(vault, item_id, recovered_qty)
        lost_qty = qty - recovered_qty
        if lost_qty > 0:
            lost[item_id] = lost_qty

    total_items = sum(recoverable.values())
    recovered_items = sum(recovered.values())
    status = _recovery_status(total_items, recovered_items)

    distance_tav = _distance_tav(state.distance)
    rare_bonus = _rare_item_bonus(recovered, content)
    milestone_bonus, milestone_awards = _milestone_bonus(vault, state.distance)
    penalty_adjustment = 0
    tav_gain = distance_tav + rare_bonus + milestone_bonus
    if status == "lost":
        penalty_adjustment = -3
        tav_gain = max(0, tav_gain + penalty_adjustment)

    vault.tav += tav_gain
    vault.vault_level = max(1, 1 + vault.tav // 75)

    return DroneRecoveryReport(
        status=status,
        recovery_chance=recovery_chance,
        recovered=recovered,
        lost=lost,
        tav_gain=tav_gain,
        milestone_awards=milestone_awards,
        distance_tav=distance_tav,
        rare_bonus=rare_bonus,
        milestone_bonus=milestone_bonus,
        penalty_adjustment=penalty_adjustment,
    )
