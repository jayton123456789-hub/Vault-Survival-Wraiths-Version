from __future__ import annotations

from typing import Any

from .loader import ContentBundle
from .models import GameState, LogEntry, clamp_meter, make_log_entry
from .rng import DeterministicRNG, WeightedEntry
from .travel import apply_death_checks


def _add_inventory_item(state: GameState, item_id: str, qty: int) -> None:
    state.inventory[item_id] = state.inventory.get(item_id, 0) + qty


def _remove_inventory_item(state: GameState, item_id: str, qty: int) -> int:
    current = state.inventory.get(item_id, 0)
    removed = min(current, qty)
    remaining = current - removed
    if remaining > 0:
        state.inventory[item_id] = remaining
    else:
        state.inventory.pop(item_id, None)
    return removed


def _total_injury_resist(state: GameState, content: ContentBundle) -> float:
    resist = 0.0
    for item_id in state.equipped.as_values():
        item = content.item_by_id.get(item_id)
        if item:
            resist += item.modifiers.injuryResist or 0.0
    return max(0.0, min(0.95, resist))


def _apply_loot_roll(
    state: GameState,
    payload: dict[str, Any],
    content: ContentBundle,
    rng: DeterministicRNG,
) -> list[LogEntry]:
    logs: list[LogEntry] = []
    table_id = payload["lootTableId"]
    table = content.loottable_by_id[table_id]
    rolls = int(payload.get("rolls", table.rolls))

    for guaranteed in table.guaranteed:
        _add_inventory_item(state, guaranteed.item_id, guaranteed.qty)
        logs.append(make_log_entry(state, "outcome", f"Guaranteed loot: {guaranteed.qty}x {guaranteed.item_id}."))

    weighted_entries = [WeightedEntry(value=entry, weight=entry.weight) for entry in table.entries]
    for _ in range(rolls):
        selected_entry = rng.pick_weighted(weighted_entries)
        min_qty = selected_entry.min_qty or 1
        max_qty = selected_entry.max_qty or min_qty
        qty = min_qty if max_qty == min_qty else rng.next_int(min_qty, max_qty + 1)
        _add_inventory_item(state, selected_entry.item_id, qty)
        logs.append(make_log_entry(state, "outcome", f"Loot roll: {qty}x {selected_entry.item_id}."))

    return logs


def apply_outcomes(
    state: GameState,
    outcomes: list[dict[str, Any]],
    content: ContentBundle,
    rng: DeterministicRNG,
) -> list[LogEntry]:
    logs: list[LogEntry] = []

    for outcome in outcomes:
        if state.dead:
            break
        was_dead = state.dead
        (op, value), = outcome.items()

        if op == "addItems":
            for entry in value:
                item_id = entry["itemId"]
                qty = int(entry["qty"])
                _add_inventory_item(state, item_id, qty)
                logs.append(make_log_entry(state, "outcome", f"Gained {qty}x {item_id}."))

        elif op == "removeItems":
            for entry in value:
                item_id = entry["itemId"]
                qty = int(entry["qty"])
                removed = _remove_inventory_item(state, item_id, qty)

                remaining = qty - removed
                if remaining > 0:
                    for slot_name in ("pack", "armor", "vehicle", "utility1", "utility2", "faction"):
                        if remaining <= 0:
                            break
                        equipped_item = getattr(state.equipped, slot_name)
                        if equipped_item == item_id:
                            setattr(state.equipped, slot_name, None)
                            remaining -= 1

                logs.append(make_log_entry(state, "outcome", f"Removed {qty - remaining}x {item_id}."))

        elif op == "setFlags":
            for flag in value:
                state.flags.add(flag)
            logs.append(make_log_entry(state, "outcome", f"Flags set: {', '.join(value)}."))

        elif op == "unsetFlags":
            for flag in value:
                state.flags.discard(flag)
            logs.append(make_log_entry(state, "outcome", f"Flags cleared: {', '.join(value)}."))

        elif op == "metersDelta":
            for meter_name, delta in value.items():
                current = getattr(state.meters, meter_name)
                setattr(state.meters, meter_name, clamp_meter(current + float(delta)))
            logs.append(
                make_log_entry(
                    state,
                    "outcome",
                    "Meters changed: "
                    f"stamina {value.get('stamina', 0)}, "
                    f"hydration {value.get('hydration', 0)}, "
                    f"morale {value.get('morale', 0)}.",
                )
            )

        elif op == "addInjury":
            delta = float(value)
            resist = _total_injury_resist(state, content)
            effective_delta = delta if delta < 0 else delta * (1.0 - resist)
            state.injury = max(0.0, min(100.0, state.injury + effective_delta))
            logs.append(
                make_log_entry(
                    state,
                    "outcome",
                    (
                        f"Injury changed by {effective_delta:.2f} "
                        f"(raw {delta:.2f}, resist {(resist * 100):.0f}%)."
                    ),
                )
            )

        elif op == "setDeathChance":
            chance = float(value)
            roll = rng.next_float()
            if roll < chance:
                state.dead = True
                state.death_reason = f"Fatal outcome roll ({chance * 100:.1f}% chance)."
                logs.append(
                    make_log_entry(
                        state,
                        "death",
                        f"Death chance triggered ({chance * 100:.1f}% chance, roll {roll:.4f}).",
                    )
                )
            else:
                logs.append(
                    make_log_entry(
                        state,
                        "outcome",
                        f"Survived death chance ({chance * 100:.1f}% chance, roll {roll:.4f}).",
                    )
                )

        elif op == "lootRoll":
            logs.extend(_apply_loot_roll(state, value, content, rng))

        else:
            raise ValueError(f"Unsupported outcome operator '{op}'.")

        if not was_dead and not state.dead:
            death_reason = apply_death_checks(state)
            if death_reason:
                logs.append(make_log_entry(state, "death", f"Runner died: {death_reason}."))

    return logs
