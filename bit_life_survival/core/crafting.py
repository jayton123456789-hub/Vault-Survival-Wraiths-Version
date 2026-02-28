from __future__ import annotations

from typing import Iterable

from .models import Recipe, VaultState
from .persistence import store_item, take_item
from .rng import DeterministicRNG

MILESTONE_UNLOCKS: tuple[tuple[int, str], ...] = (
    (10, "filter_mask_recipe"),
    (18, "lockpick_set_recipe"),
    (26, "med_armband_recipe"),
    (36, "radio_parts_recipe"),
    (48, "repair_kit_recipe"),
    (62, "water_purifier_recipe"),
)


def can_craft(vault: VaultState, recipe: Recipe) -> tuple[bool, dict[str, tuple[int, int]]]:
    requirements: dict[str, tuple[int, int]] = {}
    craftable = True
    for item_id, required in recipe.inputs.items():
        if item_id in vault.materials:
            available = int(vault.materials.get(item_id, 0))
        else:
            available = int(vault.storage.get(item_id, 0))
        requirements[item_id] = (available, int(required))
        if available < required:
            craftable = False
    return craftable, requirements


def craft(vault: VaultState, recipe: Recipe) -> bool:
    craftable, requirements = can_craft(vault, recipe)
    if not craftable:
        return False
    for item_id, (_, required) in requirements.items():
        if not take_item(vault, item_id, required):
            return False
    store_item(vault, recipe.output_item, recipe.output_qty)
    return True


def recipe_dict(recipes: Iterable[Recipe]) -> dict[str, Recipe]:
    return {recipe.id: recipe for recipe in recipes}


def unlocked_recipes(vault: VaultState, recipes: Iterable[Recipe]) -> list[Recipe]:
    recipe_lookup = recipe_dict(recipes)
    return [recipe_lookup[recipe_id] for recipe_id in sorted(vault.blueprints) if recipe_id in recipe_lookup]


def locked_recipes(vault: VaultState, recipes: Iterable[Recipe]) -> list[Recipe]:
    return [recipe for recipe in recipes if recipe.id not in vault.blueprints]


def apply_milestone_blueprints(vault: VaultState) -> list[str]:
    newly_unlocked: list[str] = []
    for required_tav, recipe_id in MILESTONE_UNLOCKS:
        if vault.tav < required_tav:
            continue
        if recipe_id in vault.blueprints:
            continue
        vault.blueprints.add(recipe_id)
        newly_unlocked.append(recipe_id)
    return newly_unlocked


def maybe_award_blueprint_drop(
    vault: VaultState,
    recipes: Iterable[Recipe],
    distance: float,
    rng_state: int,
    rng_calls: int,
) -> str | None:
    locked = [recipe.id for recipe in recipes if recipe.id not in vault.blueprints]
    if not locked:
        return None
    if distance < 12:
        return None

    if distance >= 40:
        chance = 0.50
    elif distance >= 28:
        chance = 0.34
    elif distance >= 18:
        chance = 0.22
    else:
        chance = 0.12

    mixed_state = (int(rng_state) ^ 0x9E3779B9) & 0xFFFFFFFF
    if mixed_state <= 0:
        mixed_state = 1
    rng = DeterministicRNG(
        seed=f"{vault.settings.base_seed}:blueprint_drop",
        state=mixed_state,
        calls=max(0, int(rng_calls)),
    )
    if rng.next_float() > chance:
        return None
    selected = locked[rng.next_int(0, len(locked))]
    vault.blueprints.add(selected)
    return selected
