from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text

from .core import Scene


class MainMenuScene(Scene):
    def __init__(self, message: str = "") -> None:
        self.message = message
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        center = anchored_rect(app.screen.get_rect(), (420, 430), "center")
        rows = split_rows(pygame.Rect(center.left + 20, center.top + 80, center.width - 40, center.height - 100), [1, 1, 1, 1, 1], gap=12)
        self.buttons = [
            Button(rows[0], "Continue", hotkey=pygame.K_c, on_click=lambda: self._continue(app)),
            Button(rows[1], "New Game", hotkey=pygame.K_n, on_click=lambda: self._new_game(app)),
            Button(rows[2], "Load Game", hotkey=pygame.K_l, on_click=lambda: self._load_game(app)),
            Button(rows[3], "Settings", hotkey=pygame.K_s, on_click=lambda: self._settings(app)),
            Button(rows[4], "Exit to Desktop", hotkey=pygame.K_ESCAPE, on_click=app.quit),
        ]
        self.buttons[0].enabled = app.save_service.last_slot() is not None and any(
            summary.slot == app.save_service.last_slot() and summary.occupied for summary in app.save_service.list_slots()
        )

    def _continue(self, app) -> None:
        slot = app.save_service.last_slot()
        if slot is None:
            self.message = "No previous save slot found."
            return
        if not app.save_service.slot_exists(slot):
            self.message = f"Last slot ({slot}) not found."
            return
        app.load_slot(slot)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _new_game(self, app) -> None:
        from .new_game import NewGameScene

        app.change_scene(NewGameScene())

    def _load_game(self, app) -> None:
        from .load_game import LoadGameScene

        app.change_scene(LoadGameScene())

    def _settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: MainMenuScene(message=self.message)))

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                return

    def render(self, app, surface: pygame.Surface) -> None:
        surface.fill(theme.COLOR_BG)
        self._build_layout(app)

        title_font = theme.get_font(56, bold=True)
        draw_text(surface, "Bit Life Survival", title_font, theme.COLOR_TEXT, (surface.get_width() // 2, 90), "center")
        draw_text(
            surface,
            "Phase 2 Window UI",
            theme.get_font(20),
            theme.COLOR_TEXT_MUTED,
            (surface.get_width() // 2, 128),
            "center",
        )

        panel_rect = anchored_rect(surface.get_rect(), (460, 470), "center")
        Panel(panel_rect, title="Main Menu").draw(surface)
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        if self.message:
            draw_text(
                surface,
                self.message,
                theme.get_font(18),
                theme.COLOR_WARNING,
                (surface.get_width() // 2, panel_rect.bottom + 26),
                "center",
            )
