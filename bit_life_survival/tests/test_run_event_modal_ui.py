from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.run import EventOverlay, RunScene, _option_preview_line
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data
from bit_life_survival.core.settings import default_settings


class _LoggerStub:
    def info(self, *_args, **_kwargs) -> None:
        return


class _BackgroundStub:
    def draw(self, surface: pygame.Surface, _biome: str) -> None:
        surface.fill((20, 20, 20))


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.window = self.screen
        self.clock = pygame.time.Clock()
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=6060)
        self.save_data.vault.settings.seen_run_help = True
        self.current_loadout = EquippedSlots()
        self.settings = default_settings()
        self.settings["gameplay"]["tutorial_completed"] = True
        self.backgrounds = _BackgroundStub()
        self.gameplay_logger = _LoggerStub()
        self.quit_after_scene = False

    def save_current_slot(self) -> None:
        return

    def save_settings(self) -> None:
        return

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)

    def change_scene(self, _scene) -> None:
        return

    def quit(self) -> None:
        return


def test_option_preview_line_summarizes_meter_and_injury_effects() -> None:
    option = SimpleNamespace(
        costs=[{"metersDelta": {"stamina": -2}}],
        outcomes=[{"metersDelta": {"hydration": +3, "morale": -1}}, {"addInjury": {"amount": 4}}],
    )
    preview = _option_preview_line(option)
    assert "S-2" in preview
    assert "H+3" in preview
    assert "M-1" in preview
    assert "Inj+4" in preview


def test_event_modal_tracks_clickable_option_rows_after_render() -> None:
    app = _AppStub()
    scene = RunScene(run_seed=77, auto_step_once=False)
    scene.on_enter(app)
    for _ in range(30):
        if scene.event_overlay is not None or (scene.state and scene.state.dead):
            break
        scene._continue_step(app)
    assert scene.event_overlay is not None
    scene.render(app, app.screen)
    assert len(scene._event_option_rects) == len(scene.event_overlay.event_instance.options)


def test_event_modal_prioritizes_unlocked_options_before_bonus_locked_routes() -> None:
    app = _AppStub()
    scene = RunScene(run_seed=88, auto_step_once=False)
    scene.on_enter(app)
    assert scene.state is not None
    locked = SimpleNamespace(
        id="locked",
        label="Locked route",
        locked=True,
        lock_reasons=["Requires owned item with tag 'Medical'."],
        death_chance_hint=0.08,
        loot_bias=2,
        costs=[],
        outcomes=[],
    )
    open_option = SimpleNamespace(
        id="open",
        label="Open route",
        locked=False,
        lock_reasons=[],
        death_chance_hint=0.02,
        loot_bias=1,
        costs=[],
        outcomes=[],
    )
    event = SimpleNamespace(
        title="Test Event",
        text="Pick a route.",
        event_id="evt_test",
        tags=[],
        options=[locked, open_option],
    )
    scene.event_overlay = EventOverlay(
        event_instance=event,
        travel_delta={"stamina": 0.0, "hydration": 0.0, "morale": 0.0},
    )
    scene.render(app, app.screen)
    assert scene._event_option_indices == [1, 0]
