from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.drone_bay import DroneBayScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data, transfer_selected_citizen_to_roster
from bit_life_survival.core.settings import default_settings


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.window = self.screen
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=9090)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.backgrounds = SimpleNamespace(draw=lambda surface, _kind: surface.fill((20, 20, 20)))
        self.changed_scene = None
        self.saved_calls = 0
        self.quit_called = False
        self.running = True

    def save_current_slot(self) -> None:
        self.saved_calls += 1

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def change_scene(self, scene) -> None:
        self.changed_scene = scene

    def compute_run_seed(self) -> int:
        return 1337

    def quit(self) -> None:
        self.quit_called = True
        self.running = False


def _click(scene: DroneBayScene, app: _AppStub, button_text: str) -> None:
    button = next(button for button in scene.buttons if button.text == button_text)
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": button.rect.center})
    scene.handle_event(app, event)


def test_drone_bay_quit_event_exits_app() -> None:
    app = _AppStub()
    scene = DroneBayScene()

    scene.handle_event(app, pygame.event.Event(pygame.QUIT))

    assert app.quit_called is True
    assert app.running is False


def test_drone_bay_buttons_dispatch_upgrade_navigation_and_deploy() -> None:
    app = _AppStub()
    queue_id = app.save_data.vault.citizen_queue[0].id
    transfer_selected_citizen_to_roster(app.save_data.vault, queue_id)

    scene = DroneBayScene()
    scene._build_layout(app)

    level_before = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
    _click(scene, app, "Upgrade Drone Bay")
    assert int(app.save_data.vault.upgrades.get("drone_bay_level", 0)) == level_before + 1

    _click(scene, app, "Operations")
    assert app.changed_scene is not None
    assert app.changed_scene.__class__.__name__ == "OperationsScene"

    _click(scene, app, "Back")
    assert app.changed_scene is not None
    assert app.changed_scene.__class__.__name__ == "BaseScene"

    run_counter_before = int(app.save_data.vault.run_counter)
    _click(scene, app, "Deploy")
    assert app.changed_scene is not None
    assert app.changed_scene.__class__.__name__ == "BriefingScene"
    assert int(app.save_data.vault.run_counter) == run_counter_before + 1
