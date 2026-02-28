from __future__ import annotations

from typing import Callable

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, draw_text, wrap_text
from bit_life_survival.core.settings import default_settings

from .core import Scene


class SettingsScene(Scene):
    COMMON_RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]
    UI_SCALES = [0.85, 1.0, 1.15, 1.3]

    def __init__(self, return_scene_factory: Callable[[], Scene]) -> None:
        self.return_scene_factory = return_scene_factory
        self.tab = "gameplay"
        self.buttons: list[Button] = []
        self._tab_buttons: dict[str, Button] = {}
        self._footer_buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.message: str = ""

        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._tab_rect = pygame.Rect(0, 0, 0, 0)
        self._content_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _toggle(self, app, section: str, key: str) -> None:
        app.settings[section][key] = not bool(app.settings[section].get(key, False))
        app.save_settings()
        if section == "video":
            app.apply_video_settings()

    def _mk_setting_button(
        self,
        rect: pygame.Rect,
        label: str,
        on_click=None,
        enabled: bool = True,
        text_align: str = "left",
    ) -> Button:
        return Button(
            rect,
            label,
            on_click=on_click,
            enabled=enabled,
            allow_skin=False,
            text_align=text_align,
            text_fit_mode="ellipsis",
            max_font_role="section",
        )

    def _cycle_value(self, app, section: str, key: str, values: list) -> None:
        current = app.settings[section].get(key)
        lookup = current
        if values and isinstance(values[0], tuple) and isinstance(current, list):
            lookup = tuple(current)
        try:
            idx = values.index(lookup)
        except ValueError:
            idx = -1
        next_value = values[(idx + 1) % len(values)]
        if isinstance(next_value, tuple):
            app.settings[section][key] = [int(next_value[0]), int(next_value[1])]
        else:
            app.settings[section][key] = next_value
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
        if current > 5:
            current = 3
        app.settings["gameplay"]["save_slots"] = current
        app.save_settings()
        app.save_service = app.save_service.__class__(app.user_paths.saves, slot_count=current)

    def _resolution_choices(self) -> list[tuple[int, int]]:
        choices: list[tuple[int, int]] = list(self.COMMON_RESOLUTIONS)
        seen = set(choices)
        desktop_sizes: list[tuple[int, int]] = []
        try:
            desktop_sizes = [tuple(size) for size in pygame.display.get_desktop_sizes()]
        except pygame.error:
            desktop_sizes = []
        for size in desktop_sizes:
            if size not in seen:
                choices.append(size)
                seen.add(size)
        return choices

    def _go_back(self, app) -> None:
        app.change_scene(self.return_scene_factory())

    def _apply(self, app) -> None:
        app.save_settings()
        app.apply_video_settings()
        app._sync_vault_ui_settings()
        app.save_current_slot()
        self.message = "Settings applied."

    def _request_replay_tutorial(self, app) -> None:
        app.settings["gameplay"]["tutorial_completed"] = False
        app.settings["gameplay"]["replay_tutorial"] = True
        app.settings["gameplay"]["vault_assistant_completed"] = False
        app.settings["gameplay"]["vault_assistant_stage"] = 0
        app.settings["gameplay"]["vault_assistant_tav_briefed"] = False
        app.settings["gameplay"]["replay_vault_assistant"] = True
        setattr(app, "_vault_assistant_seen", set())
        app.save_settings()
        self.message = "Run tutorial + vault assistant will replay."

    def _reset_defaults(self, app) -> None:
        app.settings = default_settings()
        app.save_settings()
        app.apply_video_settings()
        app._sync_vault_ui_settings()
        app.save_current_slot()
        self.message = "Settings reset to defaults."

    def _add_gameplay_controls(self, app) -> None:
        body = pygame.Rect(self._left_rect.left + 10, self._left_rect.top + 34, self._left_rect.width - 20, self._left_rect.height - 44)
        rows = split_rows(body, [1, 1, 1, 1, 1, 1], gap=8)
        self.buttons.extend(
            [
                self._mk_setting_button(rows[0], f"Skip Intro: {app.settings['gameplay']['skip_intro']}", on_click=lambda: self._toggle(app, "gameplay", "skip_intro")),
                self._mk_setting_button(rows[1], f"Advanced Overlay: {app.settings['gameplay']['show_advanced_overlay']}", on_click=lambda: self._toggle(app, "gameplay", "show_advanced_overlay")),
                self._mk_setting_button(rows[2], f"Confirm Retreat: {app.settings['gameplay']['confirm_retreat']}", on_click=lambda: self._toggle(app, "gameplay", "confirm_retreat")),
                self._mk_setting_button(rows[3], f"Show Tooltips: {app.settings['gameplay'].get('show_tooltips', True)}", on_click=lambda: self._toggle(app, "gameplay", "show_tooltips")),
                self._mk_setting_button(rows[4], f"Save Slots: {app.settings['gameplay'].get('save_slots', 3)}", on_click=lambda: self._cycle_save_slots(app)),
                self._mk_setting_button(rows[5], "Replay Vault Assistant", on_click=lambda: self._request_replay_tutorial(app)),
            ]
        )

    def _add_video_controls(self, app) -> None:
        body = pygame.Rect(self._left_rect.left + 10, self._left_rect.top + 34, self._left_rect.width - 20, self._left_rect.height - 44)
        rows = split_rows(body, [1, 1, 1, 1, 1], gap=8)
        res = tuple(app.settings["video"].get("resolution", [1280, 720]))
        scale = float(app.settings["video"].get("ui_scale", 1.0))
        resolution_choices = self._resolution_choices()
        if res not in resolution_choices:
            resolution_choices.append(res)
        self.buttons.extend(
            [
                self._mk_setting_button(rows[0], f"Fullscreen: {app.settings['video']['fullscreen']}", on_click=lambda: self._toggle(app, "video", "fullscreen")),
                self._mk_setting_button(rows[1], f"Resolution: {res[0]} x {res[1]}", on_click=lambda v=resolution_choices: self._cycle_value(app, "video", "resolution", v)),
                self._mk_setting_button(rows[2], f"UI Scale: {scale:.2f}", on_click=lambda: self._cycle_value(app, "video", "ui_scale", self.UI_SCALES)),
                self._mk_setting_button(rows[3], f"VSync: {bool(app.settings['video'].get('vsync', False))}", on_click=lambda: self._toggle(app, "video", "vsync")),
                self._mk_setting_button(rows[4], f"Theme: {app.settings['video'].get('ui_theme', theme.DEFAULT_THEME)}", on_click=lambda: self._cycle_value(app, "video", "ui_theme", list(theme.available_themes()))),
            ]
        )

    def _add_audio_controls(self, app) -> None:
        body = pygame.Rect(self._left_rect.left + 10, self._left_rect.top + 34, self._left_rect.width - 20, self._left_rect.height - 44)
        rows = split_rows(body, [1, 1, 1], gap=10)
        for row, key in zip(rows, ("master", "music", "sfx")):
            cols = split_columns(row, [3.2, 0.9, 0.9], gap=8)
            label = f"{key.upper()}: {app.settings['audio'][key]:.2f}"
            self.buttons.append(self._mk_setting_button(cols[0], label, enabled=False))
            self.buttons.append(self._mk_setting_button(cols[1], "-", on_click=lambda k=key: self._adjust_audio(app, k, -0.1), text_align="center"))
            self.buttons.append(self._mk_setting_button(cols[2], "+", on_click=lambda k=key: self._adjust_audio(app, k, 0.1), text_align="center"))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._tab_buttons.clear()
        self._footer_buttons = []

        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1420, max_h=860)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._tab_rect, self._content_rect, self._footer_rect = split_rows(content, [0.10, 0.78, 0.12], gap=10)
        self._left_rect, self._right_rect = split_columns(self._content_rect, [0.58, 0.42], gap=10)

        tabs = [("gameplay", "Gameplay"), ("video", "Video"), ("audio", "Audio"), ("controls", "Controls")]
        for rect, (tab_key, label) in zip(split_columns(self._tab_rect, [1, 1, 1, 1], gap=8), tabs):
            button = self._mk_setting_button(rect, label, on_click=lambda t=tab_key: setattr(self, "tab", t), text_align="center")
            self._tab_buttons[tab_key] = button
            self.buttons.append(button)

        footer_cols = split_columns(pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8), [1, 1, 1], gap=10)
        self._footer_buttons = [
            Button(
                footer_cols[0],
                "Back",
                hotkey=pygame.K_ESCAPE,
                on_click=lambda: self._go_back(app),
                skin_key="back",
                skin_render_mode="frame_text",
                max_font_role="section",
            ),
            Button(footer_cols[1], "Reset Defaults", on_click=lambda: self._reset_defaults(app), allow_skin=False),
            Button(
                footer_cols[2],
                "Apply",
                hotkey=pygame.K_RETURN,
                on_click=lambda: self._apply(app),
                skin_key="settings",
                skin_render_mode="frame_text",
                max_font_role="section",
            ),
        ]
        self.buttons.extend(self._footer_buttons)

        if self.tab == "gameplay":
            self._add_gameplay_controls(app)
        elif self.tab == "video":
            self._add_video_controls(app)
        elif self.tab == "audio":
            self._add_audio_controls(app)

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        body = SectionCard(self._right_rect, "Inspector").draw(surface)
        lines: list[str]
        if self.tab == "gameplay":
            lines = [
                "Gameplay toggles control clarity and safety prompts.",
                "Confirm Retreat is recommended to avoid accidental exits.",
                "Replay Vault Assistant restarts in-base guided onboarding.",
            ]
        elif self.tab == "video":
            res = tuple(app.settings["video"].get("resolution", [1280, 720]))
            lines = [
                f"Current resolution: {res[0]} x {res[1]}",
                "2560x1440 is fully supported for high-density displays.",
                "UI Scale adjusts text and panel rhythm without changing simulation.",
            ]
        elif self.tab == "audio":
            lines = [
                "Master controls total output volume.",
                "Music and SFX channels can be tuned independently.",
                "Changes are applied immediately.",
            ]
        else:
            lines = [
                "Run Controls:",
                "C Continue  |  L Log  |  R Retreat  |  E Use Aid",
                "Q Quit  |  H Help  |  1-4 Option Picks",
                "Mouse click also selects event options.",
            ]
        y = body.top
        for line in lines:
            for wrapped in wrap_text(line, theme.get_role_font("body"), body.width):
                draw_text(surface, wrapped, theme.get_role_font("body"), theme.COLOR_TEXT_MUTED if self.tab != "controls" else theme.COLOR_TEXT, (body.left, y))
                y += theme.FONT_SIZE_BODY + 4

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Settings").draw(surface)

        SectionCard(self._tab_rect, "Control Groups").draw(surface)
        SectionCard(self._left_rect, self.tab.title()).draw(surface)
        self._draw_right_panel(app, surface)

        mouse_pos = app.virtual_mouse_pos()
        for tab_key, button in self._tab_buttons.items():
            if tab_key == self.tab:
                button.bg = theme.COLOR_ACCENT_SOFT
                button.bg_hover = theme.COLOR_ACCENT
                button.text_override_color = theme.COLOR_TEXT
            else:
                button.bg = theme.COLOR_PANEL_ALT
                button.bg_hover = theme.COLOR_ACCENT_SOFT
                button.text_override_color = None
            button.draw(surface, mouse_pos)

        for button in self.buttons:
            if button in self._tab_buttons.values() or button in self._footer_buttons:
                continue
            button.draw(surface, mouse_pos)

        CommandStrip(self._footer_rect, self._footer_buttons).draw(surface, mouse_pos)

        if self.message:
            draw_text(surface, self.message, theme.get_role_font("body", bold=True), theme.COLOR_SUCCESS, (self._panel_rect.centerx, self._panel_rect.bottom - 18), "center")
