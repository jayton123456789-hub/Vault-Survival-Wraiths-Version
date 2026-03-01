from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, draw_text, wrap_text
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
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._cards_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1420, max_h=860)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._cards_rect, self._footer_rect = split_rows(content, [0.84, 0.16], gap=10)
        footer_cols = split_columns(pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8), [1, 1], gap=10)
        self.buttons = [
            Button(
                footer_cols[0],
                "Return to Base",
                hotkey=pygame.K_b,
                on_click=lambda: self._go_base(app),
                skin_key="deploy",
                skin_render_mode="frame_text",
                max_font_role="section",
            ),
            Button(
                footer_cols[1],
                "Main Menu",
                hotkey=pygame.K_m,
                on_click=lambda: self._go_menu(app),
                skin_key="main_menu",
                skin_render_mode="frame_text",
                max_font_role="section",
            ),
        ]

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

    def _draw_summary(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        body = SectionCard(rect, "Outcome Summary").draw(surface)
        y = body.top
        draw_text(surface, self.final_state.death_reason or "Unknown", theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_WARNING, (body.left, y))
        y += 28
        draw_text(surface, f"Distance {self.final_state.distance:.2f} mi  |  Time {self.final_state.time} ticks", theme.get_role_font("body"), theme.COLOR_TEXT, (body.left, y))
        y += 22
        draw_text(surface, f"Recovery Status: {self.recovery_report.status}", theme.get_role_font("body", bold=True), theme.COLOR_TEXT, (body.left, y))
        y += 22
        draw_text(surface, f"Body retrieval chance {self.recovery_report.recovery_chance:.2f}", theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (body.left, y))
        y += 18
        failure_line = f"Severe failure risk {self.recovery_report.severe_failure_chance:.2f}"
        if self.recovery_report.severe_failure:
            failure_line += " -> triggered"
        draw_text(surface, failure_line, theme.get_role_font("meta"), theme.COLOR_WARNING if self.recovery_report.severe_failure else theme.COLOR_TEXT_MUTED, (body.left, y))

    def _draw_breakdown(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        body = SectionCard(rect, "Recovery Breakdown").draw(surface)
        y = body.top
        rows = [
            f"Scrap recovered +{self.recovery_report.scrap_recovered}",
            f"TAV gain +{self.recovery_report.tav_gain}",
            f"Distance score +{self.recovery_report.distance_tav}",
            f"Rare bonus +{self.recovery_report.rare_bonus}",
            f"Milestone bonus +{self.recovery_report.milestone_bonus}",
        ]
        if self.recovery_report.penalty_adjustment != 0:
            rows.append(f"Penalty adjustment {self.recovery_report.penalty_adjustment:+d}")
        for line in rows:
            draw_text(surface, line, theme.get_role_font("body"), theme.COLOR_TEXT, (body.left, y))
            y += theme.FONT_SIZE_BODY + 4

    def _draw_recovered_lost(self, surface: pygame.Surface, rect: pygame.Rect, title: str, values: dict[str, int], danger: bool = False) -> None:
        body = SectionCard(rect, title).draw(surface)
        y = body.top
        if not values:
            draw_text(surface, "None", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (body.left, y))
            return
        line = ", ".join(f"{item} x{qty}" for item, qty in sorted(values.items()))
        color = theme.COLOR_DANGER if danger else theme.COLOR_SUCCESS
        for wrapped in wrap_text(line, theme.get_role_font("meta"), body.width):
            draw_text(surface, wrapped, theme.get_role_font("meta"), color if danger else theme.COLOR_TEXT, (body.left, y))
            y += theme.FONT_SIZE_META + 4

    def _draw_next_steps(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        body = SectionCard(rect, "Next Actions").draw(surface)
        lines = [
            "Return to Base to re-draft and prep another run.",
            "Use Research and Operations to reduce hunger pressure and improve future recoveries.",
            "Prioritize injury mitigation, food, and water coverage before pushing deeper.",
        ]
        if self.recovery_report.blueprint_unlocks:
            lines.append(f"New blueprints: {', '.join(self.recovery_report.blueprint_unlocks)}")
        y = body.top
        for line in lines:
            for wrapped in wrap_text(line, theme.get_role_font("meta"), body.width):
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (body.left, y))
                y += theme.FONT_SIZE_META + 4

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        title = "Retreat Report" if self.retreat else "Death Report"
        Panel(self._panel_rect, title=title).draw(surface)

        top_row, bottom_row = split_rows(self._cards_rect, [0.52, 0.48], gap=10)
        top_cols = split_columns(top_row, [0.52, 0.48], gap=10)
        bottom_cols = split_columns(bottom_row, [1, 1, 1], gap=10)

        self._draw_summary(surface, top_cols[0])
        self._draw_breakdown(surface, top_cols[1])
        self._draw_recovered_lost(surface, bottom_cols[0], "Recovered", self.recovery_report.recovered, danger=False)
        self._draw_recovered_lost(surface, bottom_cols[1], "Lost", self.recovery_report.lost, danger=True)
        self._draw_next_steps(surface, bottom_cols[2])

        if self.recovery_report.milestone_awards:
            draw_text(
                surface,
                f"Milestones: {', '.join(self.recovery_report.milestone_awards)}",
                theme.get_role_font("meta", bold=True),
                theme.COLOR_WARNING,
                (self._panel_rect.left + 20, self._footer_rect.top - 10),
            )

        CommandStrip(self._footer_rect, self.buttons).draw(surface, app.virtual_mouse_pos())
