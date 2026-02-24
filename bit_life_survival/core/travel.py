from __future__ import annotations

from typing import Any

from .loader import ContentBundle
from .models import GameState, clamp_meter, make_log_entry, sync_total_injury

BASE_SPEED = 1.0
BASE_DRAIN = {
    "stamina": 4.0,
    "hydration": 5.0,
    "morale": 1.5,
}
INJURY_DEATH_THRESHOLD = 100.0


def _equipped_item_ids(state: GameState) -> list[str]:
    return state.equipped.as_values()


def apply_death_checks(state: GameState) -> str | None:
    sync_total_injury(state)
    if state.dead:
        return state.death_reason
    if state.meters.hydration <= 0:
        state.dead = True
        state.death_reason = "Dehydration"
    elif state.meters.stamina <= 0:
        state.dead = True
        state.death_reason = "Collapsed"
    elif state.injury >= INJURY_DEATH_THRESHOLD:
        state.dead = True
        state.death_reason = "Succumbed to injuries"
    return state.death_reason


def _morale_penalty_from_condition(state: GameState) -> float:
    penalty = 0.0
    if state.injury >= 65:
        penalty += 1.5
    elif state.injury >= 35:
        penalty += 0.8
    if state.meters.hydration <= 20:
        penalty += 1.4
    elif state.meters.hydration <= 35:
        penalty += 0.6
    if state.meters.stamina <= 20:
        penalty += 0.8
    return penalty


def compute_loadout_summary(state: GameState, content: ContentBundle) -> dict[str, Any]:
    equipped_items = [content.item_by_id[item_id] for item_id in _equipped_item_ids(state) if item_id in content.item_by_id]
    speed_bonus = sum(item.modifiers.speed or 0.0 for item in equipped_items)
    carry_bonus = sum(item.modifiers.carry or 0.0 for item in equipped_items)
    injury_resist = max(
        0.0,
        min(0.95, sum(item.modifiers.injuryResist or 0.0 for item in equipped_items)),
    )

    stamina_mul = 1.0
    hydration_mul = 1.0
    morale_mul = 1.0
    noise = 0.0
    tags: set[str] = set()
    for item in equipped_items:
        stamina_mul *= item.modifiers.staminaDrainMul or 1.0
        hydration_mul *= item.modifiers.hydrationDrainMul or 1.0
        morale_mul *= item.modifiers.moraleMul or 1.0
        noise += item.modifiers.noise or 0.0
        tags.update(item.tags)

    return {
        "items": equipped_items,
        "speed_bonus": speed_bonus,
        "carry_bonus": carry_bonus,
        "injury_resist": injury_resist,
        "stamina_mul": stamina_mul,
        "hydration_mul": hydration_mul,
        "morale_mul": morale_mul,
        "noise": noise,
        "tags": sorted(tags),
    }


def advance_travel(state: GameState, content: ContentBundle) -> list:
    logs: list = []
    if state.dead:
        logs.append(make_log_entry(state, "system", "Travel skipped: runner is dead."))
        return logs

    biome = content.biome_by_id.get(state.biome_id)
    if biome is None:
        raise ValueError(f"Unknown biome '{state.biome_id}' in game state.")

    loadout = compute_loadout_summary(state, content)
    speed_bonus = loadout["speed_bonus"]
    stamina_mul = loadout["stamina_mul"]
    hydration_mul = loadout["hydration_mul"]
    morale_mul = loadout["morale_mul"]

    distance_delta = max(0.0, BASE_SPEED * (1.0 + speed_bonus))
    stamina_drain = BASE_DRAIN["stamina"] * biome.meter_drain_mul.stamina * stamina_mul
    hydration_drain = BASE_DRAIN["hydration"] * biome.meter_drain_mul.hydration * hydration_mul
    morale_drain = (
        BASE_DRAIN["morale"] * biome.meter_drain_mul.morale * morale_mul + _morale_penalty_from_condition(state)
    )

    state.step += 1
    state.time += 1
    state.distance += distance_delta
    state.meters.stamina = clamp_meter(state.meters.stamina - stamina_drain)
    state.meters.hydration = clamp_meter(state.meters.hydration - hydration_drain)
    state.meters.morale = clamp_meter(state.meters.morale - morale_drain)

    logs.append(
        make_log_entry(
            state,
            "travel",
            (
                f"You traveled {distance_delta:.2f} miles through the {biome.name.lower()}. "
                f"The march drained stamina ({-stamina_drain:+.1f}), hydration ({-hydration_drain:+.1f}), "
                f"and morale ({-morale_drain:+.1f})."
            ),
            data={
                "distanceDelta": distance_delta,
                "metersDelta": {
                    "stamina": -stamina_drain,
                    "hydration": -hydration_drain,
                    "morale": -morale_drain,
                },
            },
        )
    )

    death_reason = apply_death_checks(state)
    if death_reason:
        logs.append(make_log_entry(state, "death", f"Runner died: {death_reason}."))

    return logs
