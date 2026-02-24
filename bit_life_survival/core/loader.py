from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import TypeAdapter, ValidationError

from .models import Biome, Event, Item, LootTable, METER_NAMES, Recipe

T = TypeVar("T")


class ContentValidationError(ValueError):
    def __init__(self, message: str, details: list[str] | None = None) -> None:
        self.details = details or []
        suffix = "\n".join(self.details)
        super().__init__(f"{message}\n{suffix}" if suffix else message)


@dataclass(slots=True)
class ContentBundle:
    items: list[Item]
    loottables: list[LootTable]
    biomes: list[Biome]
    events: list[Event]
    recipes: list[Recipe]
    item_by_id: dict[str, Item]
    loottable_by_id: dict[str, LootTable]
    biome_by_id: dict[str, Biome]
    event_by_id: dict[str, Event]
    recipe_by_id: dict[str, Recipe]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContentValidationError(f"Missing content file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContentValidationError(f"Invalid JSON in {path.name}: {exc.msg} at line {exc.lineno}") from exc


def _load_typed_list(path: Path, item_type: type[T]) -> list[T]:
    data = _load_json(path)
    adapter = TypeAdapter(list[item_type])  # type: ignore[index]
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        errors = []
        for issue in exc.errors():
            issue_path = ".".join(str(part) for part in issue.get("loc", [])) or "(root)"
            errors.append(f"{path.name}:{issue_path}: {issue.get('msg', 'validation error')}")
        raise ContentValidationError(f"Schema validation failed for {path.name}.", errors) from exc


def _load_optional_typed_list(path: Path, item_type: type[T]) -> list[T]:
    if not path.exists():
        return []
    return _load_typed_list(path, item_type)


def _assert_unique_ids(kind: str, values: list[Any]) -> None:
    seen: set[str] = set()
    for entry in values:
        entry_id = entry.id
        if entry_id in seen:
            raise ContentValidationError(f"Duplicate {kind} id '{entry_id}'.")
        seen.add(entry_id)


def _assert_ref(exists: bool, message: str) -> None:
    if not exists:
        raise ContentValidationError(message)


def _validate_requirement_expr(expr: Any, path: str, item_ids: set[str]) -> None:
    if not isinstance(expr, dict):
        raise ContentValidationError(f"{path} must be an object.")
    if len(expr) != 1:
        raise ContentValidationError(f"{path} must contain exactly one requirement operator.")

    (op, value), = expr.items()
    if op == "all" or op == "any":
        if not isinstance(value, list) or not value:
            raise ContentValidationError(f"{path}.{op} must be a non-empty array.")
        for index, child in enumerate(value):
            _validate_requirement_expr(child, f"{path}.{op}[{index}]", item_ids)
        return
    if op == "not":
        _validate_requirement_expr(value, f"{path}.not", item_ids)
        return
    if op in {"hasTag", "flag"}:
        if not isinstance(value, str) or not value:
            raise ContentValidationError(f"{path}.{op} must be a non-empty string.")
        return
    if op == "hasItem":
        if not isinstance(value, str) or not value:
            raise ContentValidationError(f"{path}.hasItem must be a non-empty string.")
        _assert_ref(value in item_ids, f"{path}.hasItem references missing item '{value}'.")
        return
    if op == "meterGte":
        if not isinstance(value, dict):
            raise ContentValidationError(f"{path}.meterGte must be an object.")
        meter = value.get("meter")
        threshold = value.get("value")
        if meter not in METER_NAMES:
            raise ContentValidationError(f"{path}.meterGte.meter must be one of {', '.join(METER_NAMES)}.")
        if not isinstance(threshold, (int, float)):
            raise ContentValidationError(f"{path}.meterGte.value must be numeric.")
        return
    if op in {"injuryLte", "distanceGte"}:
        if not isinstance(value, (int, float)):
            raise ContentValidationError(f"{path}.{op} must be numeric.")
        return

    raise ContentValidationError(f"{path} uses unsupported requirement operator '{op}'.")


def _validate_item_ops(
    payload: Any,
    path: str,
    item_ids: set[str],
) -> None:
    if not isinstance(payload, list) or not payload:
        raise ContentValidationError(f"{path} must be a non-empty array.")
    for idx, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ContentValidationError(f"{path}[{idx}] must be an object.")
        item_id = entry.get("itemId")
        qty = entry.get("qty")
        if not isinstance(item_id, str) or not item_id:
            raise ContentValidationError(f"{path}[{idx}].itemId must be a non-empty string.")
        _assert_ref(item_id in item_ids, f"{path}[{idx}].itemId references missing item '{item_id}'.")
        if not isinstance(qty, int) or qty <= 0:
            raise ContentValidationError(f"{path}[{idx}].qty must be a positive integer.")


def _validate_outcome(
    outcome: Any,
    path: str,
    item_ids: set[str],
    loottable_ids: set[str],
) -> None:
    if not isinstance(outcome, dict):
        raise ContentValidationError(f"{path} must be an object.")
    if len(outcome) != 1:
        raise ContentValidationError(f"{path} must contain exactly one outcome operator.")

    (op, value), = outcome.items()
    if op in {"addItems", "removeItems"}:
        _validate_item_ops(value, f"{path}.{op}", item_ids)
        return
    if op in {"setFlags", "unsetFlags"}:
        if not isinstance(value, list) or not value or not all(isinstance(flag, str) and flag for flag in value):
            raise ContentValidationError(f"{path}.{op} must be a non-empty string array.")
        return
    if op == "metersDelta":
        if not isinstance(value, dict) or not value:
            raise ContentValidationError(f"{path}.metersDelta must be a non-empty object.")
        for meter, delta in value.items():
            if meter not in METER_NAMES:
                raise ContentValidationError(f"{path}.metersDelta uses unknown meter '{meter}'.")
            if not isinstance(delta, (int, float)):
                raise ContentValidationError(f"{path}.metersDelta.{meter} must be numeric.")
        return
    if op == "addInjury":
        if not isinstance(value, (int, float)):
            raise ContentValidationError(f"{path}.addInjury must be numeric.")
        return
    if op == "setDeathChance":
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise ContentValidationError(f"{path}.setDeathChance must be between 0 and 1.")
        return
    if op == "lootRoll":
        if not isinstance(value, dict):
            raise ContentValidationError(f"{path}.lootRoll must be an object.")
        table_id = value.get("lootTableId")
        if not isinstance(table_id, str) or not table_id:
            raise ContentValidationError(f"{path}.lootRoll.lootTableId must be a non-empty string.")
        _assert_ref(
            table_id in loottable_ids,
            f"{path}.lootRoll.lootTableId references missing loot table '{table_id}'.",
        )
        rolls = value.get("rolls")
        if rolls is not None and (not isinstance(rolls, int) or rolls <= 0):
            raise ContentValidationError(f"{path}.lootRoll.rolls must be a positive integer when provided.")
        return

    raise ContentValidationError(f"{path} uses unsupported outcome operator '{op}'.")


def _validate_references(
    items: list[Item],
    loottables: list[LootTable],
    biomes: list[Biome],
    events: list[Event],
    recipes: list[Recipe],
) -> None:
    item_ids = {item.id for item in items}
    loottable_ids = {table.id for table in loottables}
    biome_ids = {biome.id for biome in biomes}

    for table in loottables:
        for idx, entry in enumerate(table.entries):
            _assert_ref(
                entry.item_id in item_ids,
                f"loottable '{table.id}' entry[{idx}] references missing item '{entry.item_id}'.",
            )
        for idx, guaranteed in enumerate(table.guaranteed):
            _assert_ref(
                guaranteed.item_id in item_ids,
                f"loottable '{table.id}' guaranteed[{idx}] references missing item '{guaranteed.item_id}'.",
            )

    for biome in biomes:
        for idx, table_id in enumerate(biome.loot_table_ids):
            _assert_ref(
                table_id in loottable_ids,
                f"biome '{biome.id}' lootTableIds[{idx}] references missing loot table '{table_id}'.",
            )

    for event in events:
        if event.trigger.biome_ids:
            for idx, biome_id in enumerate(event.trigger.biome_ids):
                _assert_ref(
                    biome_id in biome_ids,
                    f"event '{event.id}' trigger.biomeIds[{idx}] references missing biome '{biome_id}'.",
                )

        option_ids: set[str] = set()
        for option in event.options:
            if option.id in option_ids:
                raise ContentValidationError(f"event '{event.id}' has duplicate option id '{option.id}'.")
            option_ids.add(option.id)

            if option.requirements is not None:
                _validate_requirement_expr(
                    option.requirements,
                    f"event '{event.id}' option '{option.id}' requirements",
                    item_ids,
                )
            for outcome_idx, cost in enumerate(option.costs):
                _validate_outcome(
                    cost,
                    f"event '{event.id}' option '{option.id}' costs[{outcome_idx}]",
                    item_ids,
                    loottable_ids,
                )
            for outcome_idx, outcome in enumerate(option.outcomes):
                _validate_outcome(
                    outcome,
                    f"event '{event.id}' option '{option.id}' outcomes[{outcome_idx}]",
                    item_ids,
                    loottable_ids,
                )

    for recipe in recipes:
        for input_id in recipe.inputs:
            _assert_ref(
                input_id in item_ids,
                f"recipe '{recipe.id}' input references missing item '{input_id}'.",
            )
        _assert_ref(
            recipe.output_item in item_ids,
            f"recipe '{recipe.id}' output references missing item '{recipe.output_item}'.",
        )


def load_content(content_dir: Path | str) -> ContentBundle:
    base_path = Path(content_dir)
    items = _load_typed_list(base_path / "items.json", Item)
    loottables = _load_typed_list(base_path / "loottables.json", LootTable)
    biomes = _load_typed_list(base_path / "biomes.json", Biome)
    events = _load_typed_list(base_path / "events.json", Event)
    recipes = _load_optional_typed_list(base_path / "recipes.json", Recipe)

    _assert_unique_ids("item", items)
    _assert_unique_ids("loot table", loottables)
    _assert_unique_ids("biome", biomes)
    _assert_unique_ids("event", events)
    _assert_unique_ids("recipe", recipes)

    _validate_references(items, loottables, biomes, events, recipes)

    return ContentBundle(
        items=items,
        loottables=loottables,
        biomes=biomes,
        events=events,
        recipes=recipes,
        item_by_id={item.id: item for item in items},
        loottable_by_id={table.id: table for table in loottables},
        biome_by_id={biome.id: biome for biome in biomes},
        event_by_id={event.id: event for event in events},
        recipe_by_id={recipe.id: recipe for recipe in recipes},
    )
