from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.crafting import can_craft, craft
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.persistence import create_default_vault_state


def test_crafting_consumes_materials_and_produces_output() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    vault = create_default_vault_state(base_seed=123)
    recipe = content.recipe_by_id["field_pack_recipe"]

    vault.materials["scrap"] = 9
    vault.materials["cloth"] = 7
    vault.materials["plastic"] = 5
    before = dict(vault.materials)
    produced_before = vault.storage.get(recipe.output_item, 0)

    craftable, requirements = can_craft(vault, recipe)
    assert craftable is True
    assert requirements["scrap"] == (9, 4)

    assert craft(vault, recipe) is True
    assert vault.materials["scrap"] == before["scrap"] - 4
    assert vault.materials["cloth"] == before["cloth"] - 3
    assert vault.materials["plastic"] == before["plastic"] - 2
    assert vault.storage[recipe.output_item] == produced_before + 1
