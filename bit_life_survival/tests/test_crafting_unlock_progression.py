from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.crafting import apply_milestone_blueprints, maybe_award_blueprint_drop, unlocked_recipes
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.persistence import create_default_save_data


def test_default_vault_starts_with_two_core_blueprints() -> None:
    vault = create_default_save_data(base_seed=77).vault
    assert vault.blueprints == {"field_pack_recipe", "patchwork_armor_recipe"}


def test_milestone_unlocks_expand_recipes_by_tav() -> None:
    app_content = load_content(Path(__file__).resolve().parents[1] / "content")
    vault = create_default_save_data(base_seed=77).vault
    vault.tav = 20
    unlocked_now = apply_milestone_blueprints(vault)
    assert "filter_mask_recipe" in unlocked_now
    assert "lockpick_set_recipe" in unlocked_now
    unlocked = unlocked_recipes(vault, app_content.recipes)
    unlocked_ids = {recipe.id for recipe in unlocked}
    assert {"field_pack_recipe", "patchwork_armor_recipe", "filter_mask_recipe", "lockpick_set_recipe"}.issubset(unlocked_ids)


def test_blueprint_drop_requires_distance_threshold() -> None:
    app_content = load_content(Path(__file__).resolve().parents[1] / "content")
    vault = create_default_save_data(base_seed=77).vault
    before = set(vault.blueprints)
    awarded = maybe_award_blueprint_drop(vault, app_content.recipes, distance=9.0, rng_state=1234, rng_calls=4)
    assert awarded is None
    assert vault.blueprints == before
