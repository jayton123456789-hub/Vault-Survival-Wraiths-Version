from __future__ import annotations

from datetime import datetime
import math

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.avatar import draw_citizen_sprite
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, SectionCard, clamp_wrapped_lines, draw_text, wrap_text

from .core import Scene


class MainMenuScene(Scene):
    def __init__(self, message: str = "") -> None:
        self.message = message
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._hero_rect = pygame.Rect(0, 0, 0, 0)
        self._actions_rect = pygame.Rect(0, 0, 0, 0)
        self._intel_rect = pygame.Rect(0, 0, 0, 0)
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

        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1360, max_h=820)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._hero_rect, body, self._footer_rect = split_rows(content, [0.26, 0.60, 0.14], gap=10)
        self._actions_rect, self._intel_rect = split_columns(body, [0.42, 0.58], gap=10)

        action_body = pygame.Rect(self._actions_rect.left + 8, self._actions_rect.top + 28, self._actions_rect.width - 16, self._actions_rect.height - 36)
        action_rows = split_rows(action_body, [1, 1, 1, 1, 1], gap=10)
        self.buttons.append(Button(action_rows[0], "New Game", hotkey=pygame.K_n, on_click=lambda: self._new_game(app), skin_key="new_game", skin_render_mode="frame_text", max_font_role="section", tooltip="Create a new save and enter the vault."))
        self.buttons.append(Button(action_rows[1], "Continue", hotkey=pygame.K_c, on_click=lambda: self._continue(app), skin_key="continue", skin_render_mode="frame_text", max_font_role="section", tooltip="Resume your most recent save slot."))
        self.buttons.append(Button(action_rows[2], "Load Game", hotkey=pygame.K_l, on_click=lambda: self._load_game(app), allow_skin=False, max_font_role="section", tooltip="Choose a specific save slot."))
        self.buttons.append(Button(action_rows[3], "Options", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), skin_key="options", skin_render_mode="frame_text", max_font_role="section", tooltip="Adjust video, gameplay, and controls."))
        self.buttons.append(Button(action_rows[4], "Exit", hotkey=pygame.K_ESCAPE, on_click=app.quit, skin_key="exit", skin_render_mode="frame_text", max_font_role="section", tooltip="Quit to desktop."))

        summaries = app.save_service.list_slots()
        has_continue = app.save_service.last_slot() is not None and any(
            summary.slot == app.save_service.last_slot() and summary.occupied for summary in summaries
        )
        self.buttons[1].enabled = has_continue

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

    def _draw_hero(self, surface: pygame.Surface) -> None:
        hero = SectionCard(self._hero_rect, "Industrial Command").draw(surface)
        draw_text(surface, "VAULT SURVIVAL", theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_TEXT, (hero.left + 10, hero.top + 10))
        draw_text(surface, "Select protocol. Deploy teams. Recover value. Expand the vault.", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (hero.left + 12, hero.top + 36))

        t = pygame.time.get_ticks() / 1000.0
        center_x = hero.right - 120
        center_y = hero.centery + 8
        orbit = 24
        x = int(center_x + math.cos(t * 1.1) * orbit) - 26
        y = int(center_y + math.sin(t * 1.7) * 8) - 26
        draw_citizen_sprite(surface, x, y, citizen_id="menu_mascot", scale=3, selected=False, walk_phase=t * 1.5, pose="walk")

    def _draw_intel(self, app, surface: pygame.Surface) -> None:
        body = SectionCard(self._intel_rect, "Command Intel").draw(surface)
        lines = [
            "Crafting is inside Operations.",
            "Use Mission / Runner Snapshot / Vault toggles in Base.",
            "Different lanes now allow crowd pass-through.",
            "Select 2560x1440 in Settings for native monitor fit.",
        ]
        y = body.top
        bottom = body.bottom
        for line in lines:
            if y >= bottom:
                break
            wrapped, _ = clamp_wrapped_lines(line, theme.get_role_font("body"), body.width, bottom - y, line_spacing=4)
            for segment in wrapped:
                if y + theme.get_role_font("body").get_linesize() > bottom:
                    break
                draw_text(surface, segment, theme.get_role_font("body"), theme.COLOR_TEXT, (body.left, y))
                y += theme.FONT_SIZE_BODY + 4

        latest = app.save_service.last_slot()
        summaries = {entry.slot: entry for entry in app.save_service.list_slots()}
        y += 6
        draw_text(surface, "Save Snapshot", theme.get_role_font("section", bold=True, kind="display"), theme.COLOR_TEXT, (body.left, y))
        y += 28
        if latest is not None and latest in summaries and summaries[latest].occupied:
            info = summaries[latest]
            lines = [
                f"Slot {latest}  |  Vault Lv {info.vault_level}  |  TAV {info.tav}",
                f"Drone Bay {info.drone_bay_level}  |  Last Played {self._fmt_ts(info.last_played)}",
            ]
        else:
            lines = ["No active save slot.", "Start a new protocol to begin."]
        for line in lines:
            if y >= bottom:
                break
            wrapped, _ = clamp_wrapped_lines(line, theme.get_role_font("meta"), body.width, bottom - y, line_spacing=6)
            for segment in wrapped:
                if y + theme.get_role_font("meta").get_linesize() > bottom:
                    break
                draw_text(surface, segment, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (body.left, y))
                y += theme.FONT_SIZE_META + 6

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Main Command").draw(surface)

        self._draw_hero(surface)
        SectionCard(self._actions_rect, "Protocol Actions").draw(surface)
        self._draw_intel(app, surface)

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        footer = SectionCard(self._footer_rect, "Status").draw(surface)
        if self.message:
            draw_text(surface, self.message, theme.get_role_font("body", bold=True), theme.COLOR_WARNING, (footer.left, footer.top))
            return
        status = "Choose a protocol to continue."
        for idx, line in enumerate(wrap_text(status, theme.get_role_font("meta"), footer.width)):
            draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (footer.left, footer.top + idx * (theme.FONT_SIZE_META + 4)))
