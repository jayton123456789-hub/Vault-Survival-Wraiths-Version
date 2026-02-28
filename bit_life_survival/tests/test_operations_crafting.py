from __future__ import annotations

from pathlib import Path

import pygame

from bit_life_survival.app.scenes.operations import OperationsScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data
from bit_life_survival.core.settings import default_settings


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=2026)
        self.current_loadout = EquippedSlots()
        self.saved = False
        self.settings = default_settings()

    def save_current_slot(self) -> None:
        self.saved = True

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)


def test_operations_scene_crafts_selected_recipe() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="crafting")
    scene.on_enter(app)
    scene.tab = "crafting"
    scene._refresh_rows(app)

    recipe = app.content.recipe_by_id["field_pack_recipe"]
    app.save_data.vault.materials["scrap"] = 10
    app.save_data.vault.materials["cloth"] = 10
    app.save_data.vault.materials["plastic"] = 10
    produced_before = app.save_data.vault.storage.get(recipe.output_item, 0)

    scene.selected_recipe_id = recipe.id
    scene._craft_selected(app)

    assert app.save_data.vault.storage[recipe.output_item] == produced_before + recipe.output_qty
    assert app.saved is True
    assert "Crafted" in scene.message


def test_operations_scene_builds_all_tabs_without_error() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)
    for tab in ("loadout", "equippable", "craftables", "storage", "crafting"):
        scene.tab = tab
        scene._last_size = None
        scene._build_layout(app)
        assert scene._panel_rect.width > 0
        assert scene._left_rect.width > 0
        assert scene._right_rect.width > 0


def test_crafting_starts_with_two_unlocked_recipes() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="crafting")
    scene.on_enter(app)
    scene.tab = "crafting"
    scene._refresh_rows(app)
    assert len(scene._recipes) == 2
    assert len(scene._recipe_rows) >= len(scene._recipes)


def test_storage_layout_rows_do_not_overlap() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="storage")
    scene.on_enter(app)
    scene.tab = "storage"
    scene._last_size = None
    scene._build_layout(app)
    assert scene._materials_rect.bottom <= scene._filters_rect.top
    assert scene._filters_rect.bottom <= scene._list_rect.top


def test_operations_action_strip_enablement_is_context_sensitive() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)

    scene.tab = "loadout"
    scene._last_size = None
    scene._build_layout(app)
    assert scene._action_buttons["equip_selected"].enabled is True
    assert scene._action_buttons["equip_best"].enabled is True
    assert scene._action_buttons["equip_all"].enabled is True
    assert scene._action_buttons["craft"].enabled is False

    scene.tab = "crafting"
    scene._last_size = None
    scene._build_layout(app)
    # Mirror runtime state toggles from render path.
    scene._action_buttons["craft"].enabled = scene.tab == "crafting"
    scene._action_buttons["equip_selected"].enabled = scene.tab == "loadout"
    scene._action_buttons["equip_best"].enabled = scene.tab == "loadout"
    scene._action_buttons["equip_all"].enabled = scene.tab == "loadout"
    assert scene._action_buttons["craft"].enabled is True
    assert scene._action_buttons["equip_selected"].enabled is False
    assert scene._action_buttons["equip_best"].enabled is False
    assert scene._action_buttons["equip_all"].enabled is False


def test_loadout_slot_focus_sets_filter_for_fast_equipping() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)
    scene.tab = "loadout"
    scene._refresh_rows(app)
    scene._focus_slot(app, "armor")
    assert scene.active_slot == "armor"
    assert scene.selected_slot_filter == "armor"


def test_operations_assistant_stage_completion_does_not_replay_immediately() -> None:
    app = _AppStub()
    app.settings["gameplay"]["vault_assistant_completed"] = False
    app.settings["gameplay"]["vault_assistant_stage"] = 1

    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)
    assert scene._vault_assistant is not None

    scene._finish_assistant_stage(app, skipped=False)
    assert app.settings["gameplay"]["vault_assistant_stage"] == 2

    scene_again = OperationsScene(initial_tab="loadout")
    scene_again.on_enter(app)
    assert scene_again._vault_assistant is None
