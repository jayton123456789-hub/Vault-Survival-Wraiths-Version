from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from bit_life_survival.app.main import GameApp


class Scene:
    def on_enter(self, app: "GameApp") -> None:
        return

    def on_exit(self, app: "GameApp") -> None:
        return

    def handle_event(self, app: "GameApp", event: pygame.event.Event) -> None:
        return

    def update(self, app: "GameApp", dt: float) -> None:
        return

    def render(self, app: "GameApp", surface: pygame.Surface) -> None:
        return
