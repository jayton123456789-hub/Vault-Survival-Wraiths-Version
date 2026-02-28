from __future__ import annotations

import pygame

from bit_life_survival.app.scenes.settings import SettingsScene
from bit_life_survival.core.settings import default_settings


class _AppStub:
    def __init__(self) -> None:
        self.settings = default_settings()
        self.saved_calls = 0
        self.video_calls = 0

    def save_settings(self) -> None:
        self.saved_calls += 1

    def apply_video_settings(self) -> None:
        self.video_calls += 1


def test_settings_resolution_choices_include_2560_1440() -> None:
    pygame.init()
    scene = SettingsScene(return_scene_factory=lambda: None)
    choices = scene._resolution_choices()
    assert (2560, 1440) in choices


def test_cycle_value_persists_resolution_as_list() -> None:
    app = _AppStub()
    scene = SettingsScene(return_scene_factory=lambda: None)
    app.settings["video"]["resolution"] = [1920, 1080]
    scene._cycle_value(app, "video", "resolution", [(1920, 1080), (2560, 1440)])
    assert app.settings["video"]["resolution"] == [2560, 1440]
    assert app.saved_calls == 1
    assert app.video_calls == 1

