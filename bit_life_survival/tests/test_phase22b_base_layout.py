from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.base import BaseScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data
from bit_life_survival.core.settings import default_settings


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=123)
        self.current_loadout = EquippedSlots()
        self.changed_scene = None
        self.settings = default_settings()
        self.backgrounds = SimpleNamespace(draw=lambda surface, _kind: surface.fill((20, 20, 20)))

    def save_current_slot(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def change_scene(self, scene) -> None:
        self.changed_scene = scene

    def return_staged_loadout(self) -> None:
        return

    def save_settings(self) -> None:
        return


def test_base_layout_status_and_tooltip_rows_do_not_overlap() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._build_layout(app)
    assert scene._bottom_actions_rect.bottom <= scene._bottom_status_rect.top
    assert scene._context_buttons_rect.bottom <= scene._context_panel_rect.top
    assert scene._context_panel_rect.bottom <= scene._status_row_rect.top
    assert scene._bottom_status_rect.right <= scene._bottom_tooltip_rect.left


def test_base_routes_to_operations_and_drone_bay() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._open_operations(app, "crafting")
    assert app.changed_scene.__class__.__name__ == "OperationsScene"
    assert getattr(app.changed_scene, "tab", None) == "crafting"

    scene._open_drone_bay(app)
    assert app.changed_scene.__class__.__name__ == "DroneBayScene"


def test_base_uses_unified_intel_panel_and_large_room_stage() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._build_layout(app)
    labels = {button.text for button in scene.buttons}
    assert "Mission" not in labels
    assert "Runner Snapshot" not in labels
    assert "Vault" not in labels
    assert scene._context_panel_rect.height >= 110
    assert scene._intake_room_rect.height >= 180
    assert scene._deploy_room_rect.height >= 180
    assert scene._claw_controls_rect.top >= scene._selection_rect.bottom


def test_claw_uses_selected_intake_target_and_moves_that_citizen() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._build_layout(app)
    scene.claw_room.sync(app.save_data.vault.citizen_queue, app.save_data.vault.deploy_roster)
    selected = app.save_data.vault.citizen_queue[0].id
    scene.claw_room.selected_intake_id = selected
    scene._start_claw_transfer(app)
    for _ in range(240):
        scene.update(app, 1 / 60.0)
        if any(citizen.id == selected for citizen in app.save_data.vault.deploy_roster):
            break
    assert any(citizen.id == selected for citizen in app.save_data.vault.deploy_roster)


def test_base_shows_post_run_tav_assistant_once_then_marks_briefed() -> None:
    app = _AppStub()
    app.settings["gameplay"]["vault_assistant_stage"] = 3
    app.settings["gameplay"]["vault_assistant_completed"] = True
    app.save_data.vault.run_counter = 1
    app.save_data.vault.last_run_distance = 3.5
    app.save_data.vault.last_run_time = 4

    scene = BaseScene()
    scene.on_enter(app)
    assert scene._vault_assistant is not None
    assert scene._assistant_mode == "post_run"

    scene._finish_assistant_stage(app, skipped=False)
    assert app.settings["gameplay"]["vault_assistant_tav_briefed"] is True

    scene_again = BaseScene()
    scene_again.on_enter(app)
    assert scene_again._vault_assistant is None


def test_base_mission_context_includes_next_run_profile_preview() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._build_layout(app)
    assert scene.active_context == "mission"
    surface = app.screen
    scene.render(app, surface)
