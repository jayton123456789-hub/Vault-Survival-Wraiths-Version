from __future__ import annotations

import os

from bit_life_survival.app.intro import play_intro

from .core import Scene


class IntroScene(Scene):
    def __init__(self) -> None:
        self._completed = False

    def update(self, app, dt: float) -> None:
        if self._completed:
            return
        self._completed = True

        skip_env = os.environ.get("BLS_SKIP_INTRO", "").strip().lower() in {"1", "true", "yes", "on"}
        if app.settings["gameplay"]["skip_intro"] or skip_env:
            app.logger.info("Intro skipped by settings/env.")
        else:
            try:
                play_intro(
                    screen=app.window,
                    clock=app.clock,
                    assets_dir=app.assets_intro_dir,
                    allow_skip=True,
                    enable_cinematic_audio=True,
                )
                app.logger.info("Intro playback completed.")
            except Exception:
                app.logger.exception("Intro playback failed; continuing to menu.")

        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())
