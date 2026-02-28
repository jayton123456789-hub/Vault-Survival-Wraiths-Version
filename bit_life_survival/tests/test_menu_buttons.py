from __future__ import annotations

from dataclasses import dataclass

import pygame

from bit_life_survival.app.scenes.menu import MainMenuScene


@dataclass
class _SlotSummary:
    slot: int
    occupied: bool
    vault_level: int = 1
    tav: int = 0
    drone_bay_level: int = 0
    last_played: str | None = None


class _SaveServiceStub:
    def __init__(self, last_slot: int | None, occupied: bool) -> None:
        self._last_slot = last_slot
        self._occupied = occupied

    def last_slot(self) -> int | None:
        return self._last_slot

    def slot_exists(self, slot: int) -> bool:
        return self._last_slot == slot and self._occupied

    def list_slots(self) -> list[_SlotSummary]:
        if self._last_slot is None:
            return []
        return [_SlotSummary(slot=self._last_slot, occupied=self._occupied)]


class _AppStub:
    def __init__(self, last_slot: int | None, occupied: bool) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.save_service = _SaveServiceStub(last_slot=last_slot, occupied=occupied)

    def quit(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)


def test_menu_buttons_use_frame_text_mode_and_load_game_stays_procedural() -> None:
    app = _AppStub(last_slot=None, occupied=False)
    scene = MainMenuScene()
    scene._build_layout(app)
    by_text = {button.text: button for button in scene.buttons}

    assert by_text["New Game"].skin_render_mode == "frame_text"
    assert by_text["Continue"].skin_render_mode == "frame_text"
    assert by_text["Options"].skin_render_mode == "frame_text"
    assert by_text["Exit"].skin_render_mode == "frame_text"
    assert by_text["Load Game"].allow_skin is False


def test_menu_continue_enables_only_when_recent_slot_is_occupied() -> None:
    app_empty = _AppStub(last_slot=1, occupied=False)
    scene_empty = MainMenuScene()
    scene_empty._build_layout(app_empty)
    assert {button.text: button for button in scene_empty.buttons}["Continue"].enabled is False

    app_ready = _AppStub(last_slot=1, occupied=True)
    scene_ready = MainMenuScene()
    scene_ready._build_layout(app_ready)
    assert {button.text: button for button in scene_ready.buttons}["Continue"].enabled is True
