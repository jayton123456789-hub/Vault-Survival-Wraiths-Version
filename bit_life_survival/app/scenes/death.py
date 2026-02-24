from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_columns
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text, wrap_text
from bit_life_survival.core.drone import DroneRecoveryReport
from bit_life_survival.core.models import GameState, LogEntry

from .core import Scene


class DeathScene(Scene):
    def __init__(
        self,
        final_state: GameState,
        recovery_report: DroneRecoveryReport,
        logs: list[LogEntry],
        retreat: bool = False,
    ) -> None:
        self.final_state = final_state
        self.recovery_report = recovery_report
        self.logs = logs
        self.retreat = retreat
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        panel = anchored_rect(app.screen.get_rect(), (940, 620))
        footer = pygame.Rect(panel.left + 20, panel.bottom - 56, panel.width - 40, 42)
        cols = split_columns(footer, [1, 1], gap=12)
        self.buttons = [
            Button(cols[0], "Return to Base", hotkey=pygame.K_b, on_click=lambda: self._go_base(app)),
            Button(cols[1], "Main Menu", hotkey=pygame.K_m, on_click=lambda: self._go_menu(app)),
        ]
        self._panel_rect = panel

    def _go_base(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _go_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

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
        surface.fill(theme.COLOR_BG)
        title = "Retreat Report" if self.retreat else "Death Report"
        Panel(self._panel_rect, title=title).draw(surface)

        reason = self.final_state.death_reason or "Unknown"
        y = self._panel_rect.top + 50
        draw_text(surface, f"Reason: {reason}", theme.get_font(24, bold=True), theme.COLOR_TEXT, (self._panel_rect.left + 20, y))
        y += 34
        draw_text(surface, f"Distance: {self.final_state.distance:.2f}   Time: {self.final_state.time}", theme.get_font(20), theme.COLOR_TEXT, (self._panel_rect.left + 20, y))
        y += 32
        draw_text(surface, f"Drone Recovery: {self.recovery_report.status} (chance {self.recovery_report.recovery_chance:.2f})", theme.get_font(20), theme.COLOR_TEXT, (self._panel_rect.left + 20, y))
        y += 30
        draw_text(surface, f"TAV gain: +{self.recovery_report.tav_gain}", theme.get_font(20), theme.COLOR_SUCCESS, (self._panel_rect.left + 20, y))
        y += 32

        recovered = ", ".join(f"{k}x{v}" for k, v in sorted(self.recovery_report.recovered.items())) or "-"
        lost = ", ".join(f"{k}x{v}" for k, v in sorted(self.recovery_report.lost.items())) or "-"
        draw_text(surface, "Recovered:", theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._panel_rect.left + 20, y))
        y += 22
        for line in wrap_text(recovered, theme.get_font(16), self._panel_rect.width - 40):
            draw_text(surface, line, theme.get_font(16), theme.COLOR_TEXT_MUTED, (self._panel_rect.left + 20, y))
            y += 20
        y += 6
        draw_text(surface, "Lost:", theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._panel_rect.left + 20, y))
        y += 22
        for line in wrap_text(lost, theme.get_font(16), self._panel_rect.width - 40):
            draw_text(surface, line, theme.get_font(16), theme.COLOR_TEXT_MUTED, (self._panel_rect.left + 20, y))
            y += 20

        if self.recovery_report.milestone_awards:
            y += 8
            draw_text(surface, f"Milestones: {', '.join(self.recovery_report.milestone_awards)}", theme.get_font(16), theme.COLOR_WARNING, (self._panel_rect.left + 20, y))

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)
