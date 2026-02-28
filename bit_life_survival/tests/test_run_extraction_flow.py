from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.run import RunScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data
from bit_life_survival.core.settings import default_settings


class _LoggerStub:
    def info(self, *_args, **_kwargs) -> None:
        return


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.window = self.screen
        self.clock = pygame.time.Clock()
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=8080)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.gameplay_logger = _LoggerStub()
        self.quit_after_scene = False
        self.changed_scene = None

    def save_current_slot(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def change_scene(self, scene) -> None:
        self.changed_scene = scene


def test_run_extraction_transitions_to_victory_scene() -> None:
    app = _AppStub()
    scene = RunScene(run_seed=77, auto_step_once=False)
    scene.on_enter(app)
    assert scene.state is not None
    scene.state.distance = 15.0
    scene._extract(app)
    scene._finalize_if_finished(app)
    assert app.changed_scene is not None
    assert app.changed_scene.__class__.__name__ == "VictoryScene"
