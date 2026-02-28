from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from bit_life_survival.app.scenes.briefing import BriefingScene
from bit_life_survival.app.scenes.run import RunScene
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import EquippedSlots
from bit_life_survival.core.persistence import create_default_save_data


class _AppStub:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.Surface((1280, 720))
        self.content = load_content(Path(__file__).resolve().parents[1] / "content")
        self.save_data = create_default_save_data(base_seed=4242)
        self.current_loadout = EquippedSlots()
        self.changed_scene = None
        self.backgrounds = SimpleNamespace(draw=lambda surface, _biome: surface.fill((20, 20, 20)))

    def change_scene(self, scene) -> None:
        self.changed_scene = scene

    def virtual_mouse_pos(self) -> tuple[int, int]:
        return (0, 0)


def test_briefing_respects_explicit_biome() -> None:
    app = _AppStub()
    explicit = sorted(app.content.biome_by_id.keys())[0]
    scene = BriefingScene(run_seed=100, biome_id=explicit)
    assert scene._resolve_biome(app) == explicit


def test_briefing_auto_biome_is_deterministic_for_seed() -> None:
    app = _AppStub()
    scene_a = BriefingScene(run_seed=555, biome_id=None)
    scene_b = BriefingScene(run_seed=555, biome_id=None)
    biome_a = scene_a._resolve_biome(app)
    biome_b = scene_b._resolve_biome(app)
    assert biome_a == biome_b
    assert biome_a in app.content.biome_by_id

    scene_a._begin_run(app)
    assert isinstance(app.changed_scene, RunScene)
    assert app.changed_scene.biome_id == biome_a


def test_briefing_route_button_selection_overrides_auto_choice() -> None:
    app = _AppStub()
    scene = BriefingScene(run_seed=777, biome_id=None)
    scene._build_layout(app)
    options = sorted(app.content.biome_by_id.keys())
    assert options
    forced = options[-1]
    scene._set_biome(forced)
    scene._begin_run(app)
    assert isinstance(app.changed_scene, RunScene)
    assert app.changed_scene.biome_id == forced
