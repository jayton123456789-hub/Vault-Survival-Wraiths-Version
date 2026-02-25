from __future__ import annotations

from datetime import datetime
import math

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.avatar import draw_citizen_sprite
from bit_life_survival.app.ui.layout import anchored_rect, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text, wrap_text

from .core import Scene


class MainMenuScene(Scene):
    def __init__(self, message: str = "") -> None:
        self.message = message
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._title_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _continue(self, app) -> None:
        slot = app.save_service.last_slot()
        if slot is None or not app.save_service.slot_exists(slot):
            self.message = "No recent slot found."
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

    def _open_settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: MainMenuScene(message=self.message)))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []

        self._panel_rect = anchored_rect(app.screen.get_rect(), (468, 640), "center")
        self._title_rect = pygame.Rect(
            self._panel_rect.left + 28,
            self._panel_rect.top + 22,
            self._panel_rect.width - 56,
            160,
        )
        button_area = pygame.Rect(
            self._panel_rect.left + 44,
            self._panel_rect.top + 218,
            self._panel_rect.width - 88,
            280,
        )
        rows = split_rows(button_area, [1, 1, 1, 1, 1], gap=14)
        self.buttons.append(Button(rows[0], "New Game", hotkey=pygame.K_n, on_click=lambda: self._new_game(app), tooltip="Create a new run in a save slot."))
        self.buttons.append(Button(rows[1], "Continue", hotkey=pygame.K_c, on_click=lambda: self._continue(app), tooltip="Load last played save slot."))
        self.buttons.append(Button(rows[2], "Load Game", hotkey=pygame.K_l, on_click=lambda: self._load_game(app), tooltip="Choose and load a save slot."))
        self.buttons.append(Button(rows[3], "Options", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Video, audio, and gameplay settings."))
        self.buttons.append(Button(rows[4], "Exit", hotkey=pygame.K_ESCAPE, on_click=app.quit, tooltip="Exit to desktop."))

        summaries = app.save_service.list_slots()
        has_continue = app.save_service.last_slot() is not None and any(
            summary.slot == app.save_service.last_slot() and summary.occupied for summary in summaries
        )
        self.buttons[1].enabled = has_continue

        self._footer_rect = pygame.Rect(
            self._panel_rect.left + 24,
            self._panel_rect.bottom - 76,
            self._panel_rect.width - 48,
            50,
        )

    @staticmethod
    def _fmt_ts(value: str | None) -> str:
        if not value:
            return "Never"
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect).draw(surface)
        pygame.draw.rect(surface, (64, 34, 92), self._title_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._title_rect, width=2, border_radius=2)

        draw_text(surface, "VAULT", theme.get_font(86, bold=True), (36, 22, 48), (self._panel_rect.centerx + 2, self._panel_rect.top + 82), "center")
        draw_text(surface, "SURVIVAL", theme.get_font(72, bold=True), (36, 22, 48), (self._panel_rect.centerx + 2, self._panel_rect.top + 140), "center")
        draw_text(surface, "VAULT", theme.get_font(86, bold=True), theme.COLOR_TEXT, (self._panel_rect.centerx, self._panel_rect.top + 80), "center")
        draw_text(surface, "SURVIVAL", theme.get_font(72, bold=True), theme.COLOR_TEXT, (self._panel_rect.centerx, self._panel_rect.top + 138), "center")
        t = pygame.time.get_ticks() / 1000.0
        path = [
            (self._title_rect.left + 60, self._title_rect.top + 82),
            (self._title_rect.left + 130, self._title_rect.top + 66),
            (self._title_rect.left + 210, self._title_rect.top + 74),
            (self._title_rect.left + 290, self._title_rect.top + 62),
            (self._title_rect.left + 344, self._title_rect.top + 84),
            (self._title_rect.left + 286, self._title_rect.top + 126),
            (self._title_rect.left + 220, self._title_rect.top + 136),
            (self._title_rect.left + 150, self._title_rect.top + 132),
            (self._title_rect.left + 88, self._title_rect.top + 138),
        ]
        speed = 1.8
        total = len(path)
        seg = (t * speed) % total
        i0 = int(seg)
        i1 = (i0 + 1) % total
        frac = seg - i0
        x = int(path[i0][0] + (path[i1][0] - path[i0][0]) * frac)
        y = int(path[i0][1] + (path[i1][1] - path[i0][1]) * frac - abs(math.sin(frac * math.pi)) * 7)
        draw_citizen_sprite(surface, x, y, citizen_id="menu_mascot", scale=2, selected=True, walk_phase=t * 1.7)
        draw_text(
            surface,
            "Choose a protocol to continue.",
            theme.get_font(14),
            theme.COLOR_TEXT_MUTED,
            (self._panel_rect.centerx, self._panel_rect.top + 192),
            "center",
        )

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            if button.text == "Exit":
                button.bg = (124, 64, 72)
                button.bg_hover = (162, 74, 84)
            elif button.text == "Options":
                button.bg = (130, 84, 76)
                button.bg_hover = (168, 108, 94)
            elif button.text == "Load Game":
                button.bg = (78, 104, 122)
                button.bg_hover = (108, 132, 154)
            else:
                button.bg = (78, 110, 96)
                button.bg_hover = (108, 148, 126)
            button.draw(surface, mouse_pos)

        latest = app.save_service.last_slot()
        summaries = {entry.slot: entry for entry in app.save_service.list_slots()}
        if latest is not None and latest in summaries and summaries[latest].occupied:
            info = summaries[latest]
            info_line = (
                f"Last Slot {latest}: Lv {info.vault_level} | TAV {info.tav} | "
                f"Last played {self._fmt_ts(info.last_played)}"
            )
        else:
            info_line = "No active save slot yet."
        for idx, line in enumerate(wrap_text(info_line, theme.get_font(14), self._footer_rect.width)):
            draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._footer_rect.left, self._footer_rect.top + idx * 16))

        if self.message:
            draw_text(surface, self.message, theme.get_font(16), theme.COLOR_WARNING, (self._panel_rect.centerx, self._panel_rect.bottom - 10), "midbottom")
