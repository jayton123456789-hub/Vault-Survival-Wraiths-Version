from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.base import BaseScene
from bit_life_survival.app.scenes.briefing import BriefingScene
from bit_life_survival.app.scenes.core import Scene
from bit_life_survival.app.scenes.death import DeathScene
from bit_life_survival.app.scenes.drone_bay import DroneBayScene
from bit_life_survival.app.scenes.load_game import LoadGameScene
from bit_life_survival.app.scenes.menu import MainMenuScene
from bit_life_survival.app.scenes.new_game import NewGameScene
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
            _Summary(1, True, 2, 12, 1, 8.2, 14, "2026-02-28T08:01:00Z"),
            _Summary(2, False, 0, 0, 0, 0.0, 0, None),
            _Summary(3, False, 0, 0, 0, 0.0, 0, None),
        ]

    def last_slot(self) -> int | None:
        return 1

    def slot_exists(self, slot: int) -> bool:
        return slot == 1


class _AudioStub:
    def configure(self, master: float, music: float, sfx: float) -> None:
        return


class _AppStub:
    def __init__(self, size: tuple[int, int]) -> None:
        pygame.init()
        self.screen = pygame.Surface(size)
        self.window = self.screen
        self.clock = pygame.time.Clock()
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=123)
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.save_service = _SaveServiceStub()
        self.audio = _AudioStub()
        self.user_paths = SimpleNamespace(saves=Path(__file__).resolve().parents[2] / "saves")
        self.changed_scene = None

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

    def return_staged_loadout(self) -> None:
        return

    def change_scene(self, scene) -> None:
        self.changed_scene = scene

    def compute_run_seed(self) -> int:
        return 1337

    def quit(self) -> None:
        return


def _contains(container: pygame.Rect, child: pygame.Rect) -> bool:
    return container.left <= child.left and container.top <= child.top and container.right >= child.right and container.bottom >= child.bottom


def _build_death_scene() -> DeathScene:
    final_state = GameState(seed=1, biome_id="suburbs", rng_state=1, rng_calls=0)
    report = DroneRecoveryReport(
        status="partial",
        recovery_chance=0.45,
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


def test_all_shell_scenes_stay_in_bounds_across_target_resolutions() -> None:
    resolutions = [(1280, 720), (1920, 1080), (2560, 1440)]
    for resolution in resolutions:
        app = _AppStub(resolution)
        screen = app.screen.get_rect()

        menu = MainMenuScene()
        menu._build_layout(app)
        assert _contains(screen, menu._panel_rect)

        new_game = NewGameScene()
        new_game._layout(app)
        assert _contains(screen, new_game._panel_rect)

        load_game = LoadGameScene()
        load_game._layout(app)
        assert _contains(screen, load_game._panel_rect)

        settings = SettingsScene(return_scene_factory=lambda: MainMenuScene())
        settings._build_layout(app)
        assert _contains(screen, settings._panel_rect)

        base = BaseScene()
        base._build_layout(app)
        assert _contains(screen, base._top_rect)
        assert _contains(screen, base._stage_rect)
        assert _contains(screen, base._bottom_rect)

        operations = OperationsScene(initial_tab="loadout")
        operations.on_enter(app)
        operations._build_layout(app)
        assert _contains(screen, operations._panel_rect)

        briefing = BriefingScene(run_seed=11)
        briefing._build_layout(app)
        assert _contains(screen, briefing._panel_rect)

        run = RunScene(run_seed=11)
        run._build_layout(app)
        assert _contains(screen, run.top_rect)
        assert _contains(screen, run.timeline_rect)
        assert _contains(screen, run.hud_rect)
        assert _contains(screen, run.bottom_rect)

        death = _build_death_scene()
        death._build_layout(app)
        assert _contains(screen, death._panel_rect)

        drone = DroneBayScene()
        drone._build_layout(app)
        assert _contains(screen, drone._panel_rect)


def test_interactive_shell_scenes_override_handle_event() -> None:
    interactive = [
        MainMenuScene,
        NewGameScene,
        LoadGameScene,
        SettingsScene,
        BaseScene,
        OperationsScene,
        BriefingScene,
        RunScene,
        DeathScene,
        DroneBayScene,
    ]
    for scene_cls in interactive:
        assert scene_cls.handle_event is not Scene.handle_event
