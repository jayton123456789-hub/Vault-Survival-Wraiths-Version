from __future__ import annotations

from .loader import ContentBundle
from .models import Event, GameState
from .requirements import evaluate_requirement
from .rng import DeterministicRNG, WeightedEntry
from .run_director import snapshot as director_snapshot


def _passes_trigger(event: Event, state: GameState) -> bool:
    trigger = event.trigger

    if trigger.biome_ids and state.biome_id not in trigger.biome_ids:
        return False
    if trigger.min_distance is not None and state.distance < trigger.min_distance:
        return False
    if trigger.max_distance is not None and state.distance > trigger.max_distance:
        return False
    if trigger.required_flags_all and any(flag not in state.flags for flag in trigger.required_flags_all):
        return False
    if trigger.forbidden_flags_any and any(flag in state.flags for flag in trigger.forbidden_flags_any):
        return False
    if state.event_cooldowns.get(event.id, 0) > 0:
        return False
    return True


def _tier_tag_multiplier(event: Event, tier: int) -> float:
    mult = 1.0
    tags = set(event.tags)
    if "early" in tags:
        if tier >= 3:
            mult *= 0.45
        elif tier == 2:
            mult *= 0.75
    if "mid" in tags:
        if tier == 0:
            mult *= 0.55
        elif tier >= 3:
            mult *= 1.18
    if "late" in tags:
        if tier <= 1:
            mult *= 0.38
        elif tier >= 3:
            mult *= 1.30
    if "crisis" in tags:
        if tier <= 2:
            mult *= 0.30
        else:
            mult *= 1.45
    return mult


def _option_access_multiplier(event: Event, state: GameState, content: ContentBundle) -> float:
    total = len(event.options)
    if total <= 0:
        return 0.0
    unlocked = 0
    for option in event.options:
        if option.requirements is None:
            unlocked += 1
            continue
        ok, _ = evaluate_requirement(option.requirements, state, content)
        if ok:
            unlocked += 1

    if unlocked <= 0:
        return 0.04

    ratio = unlocked / total
    mult = 0.70 + (ratio * 0.50)
    if state.step <= 2 or state.distance < 4.0:
        if unlocked == 1 and total >= 3:
            mult *= 0.55
        elif unlocked == 2 and total >= 3:
            mult *= 0.85
        elif unlocked == total:
            mult *= 1.08
    return mult


def _effective_weight(event: Event, state: GameState, content: ContentBundle) -> float:
    biome = content.biome_by_id.get(state.biome_id)
    if biome is None:
        return 0.0
    weight = event.weight
    for tag in event.tags:
        weight *= biome.event_weight_mul_by_tag.get(tag, 1.0)
    director = director_snapshot(state.distance, state.step, state.seed)
    if any(tag in {"hazard", "combat", "crisis"} for tag in event.tags):
        weight *= director.hazard_multiplier
    weight *= _tier_tag_multiplier(event, director.threat_tier)
    min_distance = float(event.trigger.min_distance or 0.0)
    if min_distance >= 12 and director.threat_tier <= 1:
        weight *= 0.35
    elif min_distance >= 8 and director.threat_tier == 0:
        weight *= 0.55
    elif min_distance <= 4 and director.threat_tier >= 3:
        weight *= 0.60
    weight *= _option_access_multiplier(event, state, content)
    return max(0.0, weight)


def _build_candidates(state: GameState, content: ContentBundle) -> list[WeightedEntry[Event]]:
    candidates = []
    for event in content.events:
        if not _passes_trigger(event, state):
            continue
        weight = _effective_weight(event, state, content)
        if weight <= 0:
            continue
        candidates.append(WeightedEntry(value=event, weight=weight))
    return candidates


def _unlocked_option_count(event: Event, state: GameState, content: ContentBundle) -> int:
    unlocked = 0
    for option in event.options:
        if option.requirements is None:
            unlocked += 1
            continue
        ok, _ = evaluate_requirement(option.requirements, state, content)
        if ok:
            unlocked += 1
    return unlocked


def select_event(state: GameState, content: ContentBundle, rng: DeterministicRNG) -> Event | None:
    candidates = _build_candidates(state, content)

    if not candidates:
        return None

    # Early run readability: prefer events with at least two playable options when possible.
    if state.step <= 3 or state.distance < 6.0:
        approachable = [
            entry
            for entry in candidates
            if _unlocked_option_count(entry.value, state, content) >= 2
        ]
        if approachable:
            candidates = approachable

    recent_ids = set(state.recent_event_ids[-6:])
    if recent_ids:
        alternatives = [entry for entry in candidates if entry.value.id not in recent_ids]
        if alternatives:
            candidates = alternatives

    # Anti-repeat safety: avoid selecting the same event consecutively when alternatives exist.
    if state.last_event_id:
        alternatives = [entry for entry in candidates if entry.value.id != state.last_event_id]
        if alternatives:
            candidates = alternatives

    return rng.pick_weighted(candidates)
