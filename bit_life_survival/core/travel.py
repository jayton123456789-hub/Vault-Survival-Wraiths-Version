from __future__ import annotations

from .loader import ContentBundle
from .models import GameState, clamp_meter, make_log_entry

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
    if state.dead:
        return state.death_reason
    if state.meters.hydration <= 0:
        state.dead = True
        state.death_reason = "Dehydration"
    elif state.meters.stamina <= 0:
        state.dead = True
        state.death_reason = "Exhaustion"
    elif state.injury >= INJURY_DEATH_THRESHOLD:
        state.dead = True
        state.death_reason = "Critical injury"
    return state.death_reason


def advance_travel(state: GameState, content: ContentBundle) -> list:
    logs = []
    if state.dead:
        logs.append(make_log_entry(state, "system", "Travel skipped: runner is dead."))
        return logs

    biome = content.biome_by_id.get(state.biome_id)
    if biome is None:
        raise ValueError(f"Unknown biome '{state.biome_id}' in game state.")

    equipped_items = [content.item_by_id[item_id] for item_id in _equipped_item_ids(state) if item_id in content.item_by_id]
    speed_bonus = sum(item.modifiers.speed or 0 for item in equipped_items)

    stamina_mul = 1.0
    hydration_mul = 1.0
    morale_mul = 1.0
    for item in equipped_items:
        stamina_mul *= item.modifiers.staminaDrainMul or 1.0
        hydration_mul *= item.modifiers.hydrationDrainMul or 1.0
        morale_mul *= item.modifiers.moraleMul or 1.0

    distance_delta = max(0.0, BASE_SPEED * (1.0 + speed_bonus))
    stamina_drain = BASE_DRAIN["stamina"] * biome.meter_drain_mul.stamina * stamina_mul
    hydration_drain = BASE_DRAIN["hydration"] * biome.meter_drain_mul.hydration * hydration_mul
    morale_drain = BASE_DRAIN["morale"] * biome.meter_drain_mul.morale * morale_mul

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
                f"Travelled {distance_delta:.2f} in '{biome.id}' "
                f"(stamina -{stamina_drain:.2f}, hydration -{hydration_drain:.2f}, morale -{morale_drain:.2f})."
            ),
        )
    )

    death_reason = apply_death_checks(state)
    if death_reason:
        logs.append(make_log_entry(state, "death", f"Runner died: {death_reason}."))

    return logs
