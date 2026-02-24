from __future__ import annotations

from typing import Iterable

from .models import Recipe, VaultState
from .persistence import store_item, take_item


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
