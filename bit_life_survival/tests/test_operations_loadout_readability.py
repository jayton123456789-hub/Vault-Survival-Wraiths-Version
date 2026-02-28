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
        self.save_data = create_default_save_data(base_seed=9090)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()

    def save_current_slot(self) -> None:
        return

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)


def test_loadout_slot_buttons_are_compact_titles_with_center_alignment() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)
    scene.tab = "loadout"
    scene._last_size = None
    scene._build_layout(app)
    scene._draw_loadout_detail(app, app.screen)
    for run_slot, button in scene._slot_buttons.items():
        assert ":" not in button.text
        assert button.text == run_slot.upper()
        assert button.text_align == "center"
