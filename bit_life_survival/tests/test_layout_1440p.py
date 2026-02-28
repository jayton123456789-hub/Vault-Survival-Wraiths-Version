from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.base import BaseScene
from bit_life_survival.app.scenes.briefing import BriefingScene
from bit_life_survival.app.scenes.death import DeathScene
from bit_life_survival.app.scenes.menu import MainMenuScene
from bit_life_survival.app.scenes.operations import OperationsScene
from bit_life_survival.app.scenes.run import RunScene
from bit_life_survival.app.scenes.settings import SettingsScene
from bit_life_survival.core.drone import DroneRecoveryReport
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots, GameState
from bit_life_survival.core.persistence import create_default_save_data
from bit_life_survival.core.settings import default_settings


@dataclass(slots=True)
class _Summary:
    slot: int
    occupied: bool
    vault_level: int
    tav: int
    drone_bay_level: int
    last_distance: float
    last_time: int
    last_played: str | None


class _SaveServiceStub:
    def __init__(self) -> None:
        self.slot_ids = (1, 2, 3)

    def list_slots(self) -> list[_Summary]:
        return [
            _Summary(1, True, 2, 10, 1, 6.5, 11, "2026-02-28T08:01:00Z"),
            _Summary(2, False, 0, 0, 0, 0.0, 0, None),
            _Summary(3, False, 0, 0, 0, 0.0, 0, None),
        ]

    def slot_exists(self, slot: int) -> bool:
        return slot == 1

    def last_slot(self) -> int | None:
        return 1


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((2560, 1440))
        self.window = self.screen
        self.clock = pygame.time.Clock()
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=123)
        self.current_loadout = EquippedSlots()
        self.changed_scene = None
        self.settings = default_settings()
        self.save_service = _SaveServiceStub()
        self.audio = SimpleNamespace(configure=lambda *args, **kwargs: None)
        self.user_paths = SimpleNamespace(saves=Path(__file__).resolve().parents[2] / "saves")

    def save_current_slot(self) -> None:
        return

    def save_settings(self) -> None:
        return

    def apply_video_settings(self) -> None:
        return

    def _sync_vault_ui_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def change_scene(self, scene) -> None:
        self.changed_scene = scene

    def return_staged_loadout(self) -> None:
        return

    def compute_run_seed(self) -> int:
        return 1234

    def quit(self) -> None:
        return


def _contains(container: pygame.Rect, child: pygame.Rect) -> bool:
    return container.left <= child.left and container.top <= child.top and container.right >= child.right and container.bottom >= child.bottom


def _death_scene() -> DeathScene:
    final_state = GameState(seed=1, biome_id="suburbs", rng_state=1, rng_calls=0)
    report = DroneRecoveryReport(
        status="partial",
        recovery_chance=0.5,
        recovered={},
        lost={},
        tav_gain=0,
        milestone_awards=[],
        blueprint_unlocks=[],
        distance_tav=0,
        rare_bonus=0,
        milestone_bonus=0,
        penalty_adjustment=0,
    )
    return DeathScene(final_state=final_state, recovery_report=report, logs=[])


def test_base_layout_stays_in_bounds_at_1440p() -> None:
    app = _AppStub()
    scene = BaseScene()
    scene._build_layout(app)
    screen_rect = app.screen.get_rect()
    assert _contains(screen_rect, scene._top_rect)
    assert _contains(screen_rect, scene._stage_rect)
    assert _contains(screen_rect, scene._bottom_rect)
    assert _contains(scene._stage_rect, scene._intake_room_rect)
    assert _contains(scene._stage_rect, scene._deploy_room_rect)


def test_base_context_and_footer_rows_stay_readable_at_1080p() -> None:
    app = _AppStub()
    app.screen = pygame.Surface((1920, 1080))
    scene = BaseScene()
    scene._build_layout(app)
    assert scene._context_panel_rect.height >= 90
    assert scene._bottom_actions_rect.bottom <= scene._context_buttons_rect.top
    assert scene._context_buttons_rect.bottom <= scene._context_panel_rect.top
    assert scene._context_panel_rect.bottom <= scene._status_row_rect.top


def test_operations_layout_stays_in_bounds_at_1440p() -> None:
    app = _AppStub()
    scene = OperationsScene(initial_tab="storage")
    scene.on_enter(app)
    scene._build_layout(app)
    screen_rect = app.screen.get_rect()
    assert _contains(screen_rect, scene._panel_rect)
    assert _contains(scene._panel_rect, scene._left_rect)
    assert _contains(scene._panel_rect, scene._right_rect)
    assert _contains(scene._left_rect, scene._list_rect)
    scene.tab = "loadout"
    scene._last_size = None
    scene._build_layout(app)
    for button in scene._slot_buttons.values():
        assert _contains(scene._detail_rect, button.rect)


def test_menu_settings_briefing_run_death_stay_in_bounds_at_1440p() -> None:
    app = _AppStub()
    screen_rect = app.screen.get_rect()

    menu = MainMenuScene()
    menu._build_layout(app)
    assert _contains(screen_rect, menu._panel_rect)

    settings = SettingsScene(return_scene_factory=lambda: MainMenuScene())
    settings._build_layout(app)
    assert _contains(screen_rect, settings._panel_rect)

    briefing = BriefingScene(run_seed=42)
    briefing._build_layout(app)
    assert _contains(screen_rect, briefing._panel_rect)

    run = RunScene(run_seed=42)
    run._build_layout(app)
    assert _contains(screen_rect, run.top_rect)
    assert _contains(screen_rect, run.timeline_rect)
    assert _contains(screen_rect, run.hud_rect)
    assert _contains(screen_rect, run.bottom_rect)

    death = _death_scene()
    death._build_layout(app)
    assert _contains(screen_rect, death._panel_rect)
