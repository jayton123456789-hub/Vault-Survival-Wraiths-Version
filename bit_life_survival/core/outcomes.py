from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .loader import ContentBundle
from .models import BODY_PARTS, GameState, LogEntry, clamp_meter, make_log_entry, sync_total_injury
from .rng import DeterministicRNG, WeightedEntry
from .travel import apply_death_checks


@dataclass(slots=True)
class OutcomeReport:
    meters_delta: dict[str, float] = field(
        default_factory=lambda: {"stamina": 0.0, "hydration": 0.0, "morale": 0.0}
    )
    injury_raw_delta: float = 0.0
    injury_effective_delta: float = 0.0
    injury_part_delta: dict[str, float] = field(default_factory=lambda: {part: 0.0 for part in BODY_PARTS})
    items_gained: dict[str, int] = field(default_factory=dict)
    items_lost: dict[str, int] = field(default_factory=dict)
    flags_set: set[str] = field(default_factory=set)
    flags_unset: set[str] = field(default_factory=set)
    death_chance_rolls: list[dict[str, float | bool]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "OutcomeReport") -> None:
        for meter_name in self.meters_delta:
            self.meters_delta[meter_name] += other.meters_delta.get(meter_name, 0.0)
        self.injury_raw_delta += other.injury_raw_delta
        self.injury_effective_delta += other.injury_effective_delta
        for part in self.injury_part_delta:
            self.injury_part_delta[part] += other.injury_part_delta.get(part, 0.0)
        for item_id, qty in other.items_gained.items():
            self.items_gained[item_id] = self.items_gained.get(item_id, 0) + qty
        for item_id, qty in other.items_lost.items():
            self.items_lost[item_id] = self.items_lost.get(item_id, 0) + qty
        self.flags_set.update(other.flags_set)
        self.flags_unset.update(other.flags_unset)
        self.death_chance_rolls.extend(other.death_chance_rolls)
        self.notes.extend(other.notes)


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


def _increment_counter(counter: dict[str, int], key: str, qty: int) -> None:
    if qty <= 0:
        return
    counter[key] = counter.get(key, 0) + qty


def _total_injury_resist(state: GameState, content: ContentBundle) -> float:
    resist = 0.0
    for item_id in state.equipped.as_values():
        item = content.item_by_id.get(item_id)
        if item:
            resist += item.modifiers.injuryResist or 0.0
    return max(0.0, min(0.95, resist))


def _pick_injury_part(state: GameState, payload: Any, rng: DeterministicRNG) -> tuple[str, float]:
    if isinstance(payload, (int, float)):
        amount = float(payload)
        part = BODY_PARTS[rng.next_int(0, len(BODY_PARTS))]
        return part, amount
    if isinstance(payload, dict):
        amount = float(payload.get("amount", 0.0))
        explicit_part = payload.get("part")
        if explicit_part in BODY_PARTS:
            return explicit_part, amount
        part = BODY_PARTS[rng.next_int(0, len(BODY_PARTS))]
        return part, amount
    raise ValueError("addInjury payload must be numeric or object.")


def _most_injured_part(state: GameState) -> str:
    ordered = sorted(BODY_PARTS, key=lambda part: state.injuries.get(part, 0.0), reverse=True)
    return ordered[0]


def _apply_targeted_heal(state: GameState, report: OutcomeReport, content: ContentBundle, item_id: str, qty: int) -> None:
    if qty <= 0:
        return
    heal_targets: list[tuple[str, float]] = []
    if item_id == "medkit_small":
        part = _most_injured_part(state)
        heal_targets.append((part, 12.0 * qty))
    elif item_id == "med_armband":
        heal_targets.append(("left_arm", 8.0 * qty))
        heal_targets.append(("right_arm", 8.0 * qty))
    elif item_id == "antiseptic":
        heal_targets.append(("torso", 6.0 * qty))
    elif item_id == "med_supplies":
        part = _most_injured_part(state)
        heal_targets.append((part, 7.0 * qty))
    if not heal_targets:
        return
    for part, amount in heal_targets:
        if amount <= 0:
            continue
        before = state.injuries.get(part, 0.0)
        healed = min(before, amount)
        if healed <= 0:
            continue
        state.injuries[part] = max(0.0, before - healed)
        report.injury_raw_delta -= healed
        report.injury_effective_delta -= healed
        report.injury_part_delta[part] -= healed
        item = content.item_by_id.get(item_id)
        label = item.name if item else item_id
        report.notes.append(f"{label} healed {part.replace('_', ' ')} by {healed:.1f}.")
    sync_total_injury(state)


def _format_item_counts(items: dict[str, int], content: ContentBundle) -> str:
    parts: list[str] = []
    for item_id, qty in sorted(items.items()):
        item = content.item_by_id.get(item_id)
        label = item.name if item else item_id
        parts.append(f"{label} x{qty}")
    return ", ".join(parts)


def _apply_loot_roll(
    state: GameState,
    payload: dict[str, Any],
    content: ContentBundle,
    rng: DeterministicRNG,
) -> dict[str, int]:
    gained: dict[str, int] = {}
    table_id = payload["lootTableId"]
    table = content.loottable_by_id[table_id]
    rolls = int(payload.get("rolls", table.rolls))

    for guaranteed in table.guaranteed:
        _add_inventory_item(state, guaranteed.item_id, guaranteed.qty)
        _increment_counter(gained, guaranteed.item_id, guaranteed.qty)

    weighted_entries = [WeightedEntry(value=entry, weight=entry.weight) for entry in table.entries]
    for _ in range(rolls):
        selected_entry = rng.pick_weighted(weighted_entries)
        min_qty = selected_entry.min_qty or 1
        max_qty = selected_entry.max_qty or min_qty
        qty = min_qty if max_qty == min_qty else rng.next_int(min_qty, max_qty + 1)
        _add_inventory_item(state, selected_entry.item_id, qty)
        _increment_counter(gained, selected_entry.item_id, qty)

    return gained


def apply_outcomes(
    state: GameState,
    outcomes: list[dict[str, Any]],
    content: ContentBundle,
    rng: DeterministicRNG,
) -> tuple[list[LogEntry], OutcomeReport]:
    logs: list[LogEntry] = []
    report = OutcomeReport()
    death_from_checks: str | None = None

    for outcome in outcomes:
        if state.dead:
            break

        (op, value), = outcome.items()

        if op == "addItems":
            for entry in value:
                item_id = entry["itemId"]
                qty = int(entry["qty"])
                _add_inventory_item(state, item_id, qty)
                _increment_counter(report.items_gained, item_id, qty)

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
                            removed += 1

                if removed > 0:
                    _increment_counter(report.items_lost, item_id, removed)
                    _apply_targeted_heal(state, report, content, item_id, removed)

        elif op == "setFlags":
            for flag in value:
                state.flags.add(flag)
                report.flags_set.add(flag)
                if flag in {"burned", "submerged", "fell", "toxic_exposure"}:
                    state.death_flags.add(flag)

        elif op == "unsetFlags":
            for flag in value:
                state.flags.discard(flag)
                report.flags_unset.add(flag)

        elif op == "metersDelta":
            for meter_name, delta in value.items():
                delta_value = float(delta)
                current = getattr(state.meters, meter_name)
                setattr(state.meters, meter_name, clamp_meter(current + delta_value))
                report.meters_delta[meter_name] = report.meters_delta.get(meter_name, 0.0) + delta_value

        elif op == "addInjury":
            part, delta = _pick_injury_part(state, value, rng)
            resist = _total_injury_resist(state, content)
            effective_delta = delta if delta < 0 else delta * (1.0 - resist)
            current_part = float(state.injuries.get(part, 0.0))
            state.injuries[part] = max(0.0, min(100.0, current_part + effective_delta))
            sync_total_injury(state)
            report.injury_raw_delta += delta
            report.injury_effective_delta += effective_delta
            report.injury_part_delta[part] += effective_delta
            if delta > 0 and resist > 0:
                prevented = delta - effective_delta
                report.notes.append(
                    f"Injury resistance reduced incoming injury by {prevented:.2f} ({part.replace('_', ' ')})."
                )

        elif op == "setDeathChance":
            chance = float(value)
            roll = rng.next_float()
            triggered = roll < chance
            report.death_chance_rolls.append({"chance": chance, "roll": roll, "triggered": triggered})
            if triggered:
                state.dead = True
                state.death_reason = f"Fatal outcome roll ({chance * 100:.1f}% chance)."

        elif op == "lootRoll":
            gained = _apply_loot_roll(state, value, content, rng)
            for item_id, qty in gained.items():
                _increment_counter(report.items_gained, item_id, qty)

        else:
            raise ValueError(f"Unsupported outcome operator '{op}'.")

        if not state.dead:
            death_reason = apply_death_checks(state)
            if death_reason:
                death_from_checks = death_reason

    if any(abs(delta) > 1e-9 for delta in report.meters_delta.values()):
        logs.append(
            make_log_entry(
                state,
                "outcome",
                (
                    "Event impact: "
                    f"stamina {report.meters_delta['stamina']:+.1f}, "
                    f"hydration {report.meters_delta['hydration']:+.1f}, "
                    f"morale {report.meters_delta['morale']:+.1f}."
                ),
                data={"metersDelta": report.meters_delta.copy()},
            )
        )

    if abs(report.injury_effective_delta) > 1e-9:
        part_bits = []
        for part in BODY_PARTS:
            delta = report.injury_part_delta.get(part, 0.0)
            if abs(delta) > 1e-9:
                part_bits.append(f"{part.replace('_', ' ')} {delta:+.1f}")
        part_text = f" Affected: {', '.join(part_bits)}." if part_bits else ""
        if report.injury_effective_delta > 0:
            injury_line = f"You were hurt (+{report.injury_effective_delta:.1f} injury).{part_text}"
        else:
            injury_line = f"You recovered ({report.injury_effective_delta:+.1f} injury).{part_text}"
        logs.append(
            make_log_entry(
                state,
                "outcome",
                injury_line,
                data={
                    "injuryRawDelta": report.injury_raw_delta,
                    "injuryEffectiveDelta": report.injury_effective_delta,
                },
            )
        )

    if report.items_gained:
        logs.append(
            make_log_entry(
                state,
                "outcome",
                f"You found: {_format_item_counts(report.items_gained, content)}.",
                data={"itemsGained": report.items_gained.copy()},
            )
        )

    if report.items_lost:
        logs.append(
            make_log_entry(
                state,
                "outcome",
                f"You lost: {_format_item_counts(report.items_lost, content)}.",
                data={"itemsLost": report.items_lost.copy()},
            )
        )

    if report.flags_set:
        logs.append(
            make_log_entry(
                state,
                "outcome",
                f"Flags set: {', '.join(sorted(report.flags_set))}.",
                data={"flagsSet": sorted(report.flags_set)},
            )
        )
    if report.flags_unset:
        logs.append(
            make_log_entry(
                state,
                "outcome",
                f"Flags cleared: {', '.join(sorted(report.flags_unset))}.",
                data={"flagsUnset": sorted(report.flags_unset)},
            )
        )

    death_from_roll_logged = False
    for entry in report.death_chance_rolls:
        chance = float(entry["chance"])
        roll = float(entry["roll"])
        triggered = bool(entry["triggered"])
        if triggered:
            death_from_roll_logged = True
            logs.append(
                make_log_entry(
                    state,
                    "death",
                    f"A fatal outcome triggered ({chance * 100:.1f}% risk, roll {roll:.4f}).",
                    data={"deathChance": chance, "roll": roll, "triggered": True},
                )
            )
        else:
            logs.append(
                make_log_entry(
                    state,
                    "outcome",
                    f"You survived a close call ({chance * 100:.1f}% risk, roll {roll:.4f}).",
                    data={"deathChance": chance, "roll": roll, "triggered": False},
                )
            )

    if death_from_checks and not death_from_roll_logged:
        logs.append(make_log_entry(state, "death", f"Runner died: {death_from_checks}."))

    return logs, report
