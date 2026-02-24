from __future__ import annotations

from dataclasses import dataclass

from bit_life_survival.core.loader import ContentBundle
from bit_life_survival.core.models import Item


RUN_SLOTS = ("pack", "armor", "vehicle", "utility1", "utility2", "faction")
RARITY_RANK = {"common": 1, "uncommon": 2, "rare": 3, "legendary": 4}
TAG_BONUS = {
    "Authority": 16.0,
    "Medical": 16.0,
    "Toxic": 18.0,
    "Stealth": 14.0,
    "Tech": 14.0,
    "Trade": 10.0,
    "Combat": 12.0,
    "Access": 12.0,
    "Tool": 8.0,
}


@dataclass(slots=True)
class ScoredChoice:
    item_id: str
    score: float
    reasons: list[str]


def allowed_item_slot(run_slot: str) -> str:
    return "utility" if run_slot in {"utility1", "utility2"} else run_slot


def score_item(item: Item) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    mods = item.modifiers

    carry = mods.carry or 0.0
    if carry:
        score += carry * 2.0
        reasons.append(f"+{carry:.0f} carry")

    injury = mods.injuryResist or 0.0
    if injury:
        score += injury * 120.0
        reasons.append(f"+{injury * 100:.0f}% injury resist")

    speed = mods.speed or 0.0
    if speed:
        score += speed * 60.0
        reasons.append(f"{speed:+.2f} speed")

    stamina_mul = mods.staminaDrainMul if mods.staminaDrainMul is not None else 1.0
    hydration_mul = mods.hydrationDrainMul if mods.hydrationDrainMul is not None else 1.0
    morale_mul = mods.moraleMul if mods.moraleMul is not None else 1.0
    noise = mods.noise or 0.0

    if stamina_mul != 1.0:
        score += (1.0 - stamina_mul) * 90.0
        reasons.append(f"stamina x{stamina_mul:.2f}")
    if hydration_mul != 1.0:
        score += (1.0 - hydration_mul) * 90.0
        reasons.append(f"hydration x{hydration_mul:.2f}")
    if morale_mul != 1.0:
        score += (1.0 - morale_mul) * 45.0
        reasons.append(f"morale x{morale_mul:.2f}")
    if noise != 0.0:
        score += -noise * 24.0
        reasons.append(f"noise {noise:+.2f}")

    for tag in item.tags:
        bonus = TAG_BONUS.get(tag, 0.0)
        if bonus:
            score += bonus
            reasons.append(f"unlocks {tag}")

    rarity_rank = RARITY_RANK.get(item.rarity, 0)
    score += rarity_rank * 2.5
    reasons.append(f"{item.rarity} tier")

    return score, reasons


def choose_best_for_slot(
    content: ContentBundle,
    storage: dict[str, int],
    run_slot: str,
    reserved: dict[str, int],
) -> ScoredChoice | None:
    allowed = allowed_item_slot(run_slot)
    candidates: list[ScoredChoice] = []
    for item_id, qty in storage.items():
        available = int(qty) - int(reserved.get(item_id, 0))
        if available <= 0:
            continue
        item = content.item_by_id.get(item_id)
        if not item or item.slot != allowed:
            continue
        score, reasons = score_item(item)
        candidates.append(ScoredChoice(item_id=item_id, score=score, reasons=reasons))

    if not candidates:
        return None

    candidates.sort(
        key=lambda choice: (
            choice.score,
            RARITY_RANK.get(content.item_by_id[choice.item_id].rarity, 0),
            content.item_by_id[choice.item_id].name,
            choice.item_id,
        ),
        reverse=True,
    )
    return candidates[0]


def format_choice_reason(content: ContentBundle, choice: ScoredChoice) -> str:
    item = content.item_by_id[choice.item_id]
    highlights = ", ".join(choice.reasons[:3])
    return f"Equipped {item.name} ({item.rarity}): {highlights}."
