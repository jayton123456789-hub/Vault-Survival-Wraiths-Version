from __future__ import annotations

from pathlib import Path

import pygame

from bit_life_survival.app.scenes.operations import OperationsScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data, transfer_selected_citizen_to_roster
from bit_life_survival.core.settings import default_settings


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=9090)
        drafted = transfer_selected_citizen_to_roster(self.save_data.vault, self.save_data.vault.citizen_queue[0].id)
        self.save_data.vault.current_citizen = drafted
        self.save_data.vault.active_deploy_citizen_id = drafted.id
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()

    def save_current_slot(self) -> None:
        return

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)


def test_loadout_slot_buttons_show_slot_name_and_equip_state() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="loadout")
    scene.on_enter(app)
    scene.tab = "loadout"
    scene._last_size = None
    scene._build_layout(app)
    scene._draw_loadout_detail(app, app.screen)
    for run_slot, button in scene._slot_buttons.items():
        assert button.text.startswith(run_slot.upper())
        assert button.text_align == "center"
        assert "✓" in button.text or "•" in button.text
