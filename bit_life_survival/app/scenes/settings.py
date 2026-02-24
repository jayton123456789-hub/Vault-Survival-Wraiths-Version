from __future__ import annotations

from typing import Callable

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_columns
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text

from .core import Scene


class SettingsScene(Scene):
    RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)]
    UI_SCALES = [0.85, 1.0, 1.15, 1.3]

    def __init__(self, return_scene_factory: Callable[[], Scene]) -> None:
        self.return_scene_factory = return_scene_factory
        self.tab = "gameplay"
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.message: str = ""

    def _toggle(self, app, section: str, key: str) -> None:
        app.settings[section][key] = not bool(app.settings[section].get(key, False))
        app.save_settings()
        if section == "video":
            app.apply_video_settings()

    def _cycle_value(self, app, section: str, key: str, values: list) -> None:
        current = app.settings[section].get(key)
        try:
            idx = values.index(current)
        except ValueError:
            idx = -1
        app.settings[section][key] = values[(idx + 1) % len(values)]
        app.save_settings()
        if section == "video":
            app.apply_video_settings()

    def _adjust_audio(self, app, key: str, delta: float) -> None:
        current = float(app.settings["audio"].get(key, 1.0))
        app.settings["audio"][key] = max(0.0, min(1.0, round(current + delta, 2)))
        app.audio.configure(
            app.settings["audio"]["master"],
            app.settings["audio"]["music"],
            app.settings["audio"]["sfx"],
        )
        app.save_settings()

    def _cycle_save_slots(self, app) -> None:
        current = int(app.settings["gameplay"].get("save_slots", 3))
        current += 1
        if current > 6:
            current = 3
        app.settings["gameplay"]["save_slots"] = current
        app.save_settings()
        app.save_service = app.save_service.__class__(app.user_paths.saves, slot_count=current)

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []

        panel_rect = anchored_rect(app.screen.get_rect(), (940, 620))
        tab_bar = pygame.Rect(panel_rect.left + 20, panel_rect.top + 50, panel_rect.width - 40, 40)
        tab_cols = split_columns(tab_bar, [1, 1, 1, 1], gap=10)
        tabs = [("gameplay", "Gameplay"), ("video", "Video"), ("audio", "Audio"), ("controls", "Controls")]
        for col, (tab_key, label) in zip(tab_cols, tabs):
            self.buttons.append(Button(col, label, on_click=lambda t=tab_key: setattr(self, "tab", t)))

        footer = pygame.Rect(panel_rect.left + 20, panel_rect.bottom - 48, panel_rect.width - 40, 34)
        footer_cols = split_columns(footer, [1, 1], gap=12)
        self.buttons.append(Button(footer_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._go_back(app)))
        self.buttons.append(Button(footer_cols[1], "Apply", hotkey=pygame.K_RETURN, on_click=lambda: self._apply(app)))

        content = pygame.Rect(panel_rect.left + 20, panel_rect.top + 105, panel_rect.width - 40, panel_rect.height - 170)

        if self.tab == "gameplay":
            rows = [pygame.Rect(content.left, content.top + i * 56, content.width, 44) for i in range(5)]
            self.buttons.append(
                Button(rows[0], f"Skip Intro: {app.settings['gameplay']['skip_intro']}", on_click=lambda: self._toggle(app, "gameplay", "skip_intro"))
            )
            self.buttons.append(
                Button(
                    rows[1],
                    f"Advanced Overlay: {app.settings['gameplay']['show_advanced_overlay']}",
                    on_click=lambda: self._toggle(app, "gameplay", "show_advanced_overlay"),
                )
            )
            self.buttons.append(
                Button(
                    rows[2],
                    f"Confirm Retreat: {app.settings['gameplay']['confirm_retreat']}",
                    on_click=lambda: self._toggle(app, "gameplay", "confirm_retreat"),
                )
            )
            self.buttons.append(
                Button(
                    rows[3],
                    f"Save Slots: {app.settings['gameplay'].get('save_slots', 3)}",
                    on_click=lambda: self._cycle_save_slots(app),
                )
            )
            self.buttons.append(
                Button(
                    rows[4],
                    "Replay Tutorial (next run)",
                    on_click=lambda: self._request_replay_tutorial(app),
                )
            )
        elif self.tab == "video":
            rows = [pygame.Rect(content.left, content.top + i * 56, content.width, 44) for i in range(3)]
            res = tuple(app.settings["video"].get("resolution", [1280, 720]))
            scale = float(app.settings["video"].get("ui_scale", 1.0))
            self.buttons.append(
                Button(rows[0], f"Fullscreen: {app.settings['video']['fullscreen']}", on_click=lambda: self._toggle(app, "video", "fullscreen"))
            )
            self.buttons.append(
                Button(rows[1], f"Resolution: {res[0]} x {res[1]}", on_click=lambda: self._cycle_value(app, "video", "resolution", self.RESOLUTIONS))
            )
            self.buttons.append(
                Button(rows[2], f"UI Scale: {scale:.2f}", on_click=lambda: self._cycle_value(app, "video", "ui_scale", self.UI_SCALES))
            )
        elif self.tab == "audio":
            rows = [pygame.Rect(content.left, content.top + i * 62, content.width, 48) for i in range(3)]
            for row, key in zip(rows, ("master", "music", "sfx")):
                cols = split_columns(row, [3, 1, 1], gap=8)
                label = f"{key.upper()}: {app.settings['audio'][key]:.2f}"
                self.buttons.append(Button(cols[0], label, enabled=False))
                self.buttons.append(Button(cols[1], "-", on_click=lambda k=key: self._adjust_audio(app, k, -0.1)))
                self.buttons.append(Button(cols[2], "+", on_click=lambda k=key: self._adjust_audio(app, k, 0.1)))
        else:
            # Controls tab uses static text.
            pass

    def _go_back(self, app) -> None:
        app.change_scene(self.return_scene_factory())

    def _apply(self, app) -> None:
        app.save_settings()
        app.apply_video_settings()
        self.message = "Settings applied."

    def _request_replay_tutorial(self, app) -> None:
        app.settings["gameplay"]["tutorial_completed"] = False
        app.settings["gameplay"]["replay_tutorial"] = True
        app.save_settings()
        self.message = "Tutorial will replay when you enter the next run."

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        surface.fill(theme.COLOR_BG)
        panel_rect = anchored_rect(surface.get_rect(), (940, 620))
        Panel(panel_rect, title="Settings").draw(surface)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        if self.tab == "controls":
            content = pygame.Rect(panel_rect.left + 24, panel_rect.top + 118, panel_rect.width - 48, panel_rect.height - 200)
            lines = [
                "C - Continue until next event",
                "L - Toggle / inspect timeline log",
                "R - Retreat to base",
                "Q - Quit to desktop",
                "H - Help",
                "1-4 - Event option shortcuts",
            ]
            y = content.top
            for line in lines:
                draw_text(surface, line, theme.get_font(20), theme.COLOR_TEXT, (content.left, y))
                y += 34

        if self.message:
            draw_text(surface, self.message, theme.get_font(18), theme.COLOR_SUCCESS, (panel_rect.centerx, panel_rect.bottom - 68), "center")
