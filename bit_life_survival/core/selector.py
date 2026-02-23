from __future__ import annotations

from .loader import ContentBundle
from .models import Event, GameState
from .rng import DeterministicRNG, WeightedEntry


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


def _effective_weight(event: Event, state: GameState, content: ContentBundle) -> float:
    biome = content.biome_by_id.get(state.biome_id)
    if biome is None:
        return 0.0
    weight = event.weight
    for tag in event.tags:
        weight *= biome.event_weight_mul_by_tag.get(tag, 1.0)
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


def select_event(state: GameState, content: ContentBundle, rng: DeterministicRNG) -> Event | None:
    candidates = _build_candidates(state, content)

    if not candidates:
        return None

    # Anti-repeat safety: avoid selecting the same event consecutively when alternatives exist.
    if state.last_event_id:
        alternatives = [entry for entry in candidates if entry.value.id != state.last_event_id]
        if alternatives:
            candidates = alternatives

    return rng.pick_weighted(candidates)
