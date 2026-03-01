from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, draw_text, wrap_text
from bit_life_survival.core.drone import DroneRecoveryReport
from bit_life_survival.core.models import GameState, LogEntry
from bit_life_survival.core.research import campaign_progress

from .core import Scene


class VictoryScene(Scene):
    def __init__(
        self,
        final_state: GameState,
        recovery_report: DroneRecoveryReport,
        logs: list[LogEntry],
    ) -> None:
        self.final_state = final_state
        self.recovery_report = recovery_report
        self.logs = logs
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._cards_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _go_base(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _go_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1420, max_h=860)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._cards_rect, self._footer_rect = split_rows(content, [0.84, 0.16], gap=10)
        footer_cols = split_columns(pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8), [1, 1], gap=10)
        self.buttons = [
            Button(footer_cols[0], "Return to Base", hotkey=pygame.K_b, on_click=lambda: self._go_base(app), skin_key="deploy", skin_render_mode="frame_text", max_font_role="section"),
            Button(footer_cols[1], "Main Menu", hotkey=pygame.K_m, on_click=lambda: self._go_menu(app), skin_key="main_menu", skin_render_mode="frame_text", max_font_role="section"),
        ]

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
        Panel(self._panel_rect, title="Extraction Success").draw(surface)

        top_row, bottom_row = split_rows(self._cards_rect, [0.48, 0.52], gap=10)
        top_cols = split_columns(top_row, [0.5, 0.5], gap=10)
        bottom_cols = split_columns(bottom_row, [1, 1], gap=10)

        summary = SectionCard(top_cols[0], "Run Outcome").draw(surface)
        y = summary.top
        draw_text(surface, "Extraction Complete", theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_SUCCESS, (summary.left, y))
        y += 30
        draw_text(surface, f"Distance {self.final_state.distance:.2f} mi", theme.get_role_font("body"), theme.COLOR_TEXT, (summary.left, y))
        y += 22
        draw_text(surface, f"Time {self.final_state.time} ticks", theme.get_role_font("body"), theme.COLOR_TEXT, (summary.left, y))
        y += 22
        draw_text(surface, f"Recovery status: {self.recovery_report.status}", theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (summary.left, y))
        y += 20
        draw_text(surface, f"Body retrieval chance {self.recovery_report.recovery_chance:.2f}", theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (summary.left, y))

        rewards = SectionCard(top_cols[1], "Reward Summary").draw(surface)
        y = rewards.top
        lines = [
            f"Scrap recovered +{self.recovery_report.scrap_recovered}",
            f"TAV gain +{self.recovery_report.tav_gain}",
            f"Distance score +{self.recovery_report.distance_tav}",
            f"Rare bonus +{self.recovery_report.rare_bonus}",
            f"Milestone bonus +{self.recovery_report.milestone_bonus}",
            f"Campaign progress {int(round(campaign_progress(app.save_data.vault) * 100))}%",
        ]
        if self.recovery_report.blueprint_unlocks:
            lines.append(f"Blueprints: {', '.join(self.recovery_report.blueprint_unlocks)}")
        for line in lines:
            for wrapped in wrap_text(line, theme.get_role_font("meta"), rewards.width):
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT, (rewards.left, y))
                y += theme.FONT_SIZE_META + 4

        recovered = SectionCard(bottom_cols[0], "Recovered Items").draw(surface)
        y = recovered.top
        if not self.recovery_report.recovered:
            draw_text(surface, "No recovered items.", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (recovered.left, y))
        else:
            text = ", ".join(f"{item} x{qty}" for item, qty in sorted(self.recovery_report.recovered.items()))
            for wrapped in wrap_text(text, theme.get_role_font("meta"), recovered.width):
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT, (recovered.left, y))
                y += theme.FONT_SIZE_META + 4

        next_steps = SectionCard(bottom_cols[1], "Next Push").draw(surface)
        y = next_steps.top
        for line in [
            "Spend scrap in Research to widen the bay, unlock contracts, and finish the campaign.",
            "Use gained rewards to improve survivability before pushing deeper checkpoints.",
            "Push past the next extraction target for bigger scrap and TAV gains.",
        ]:
            for wrapped in wrap_text(line, theme.get_role_font("meta"), next_steps.width):
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (next_steps.left, y))
                y += theme.FONT_SIZE_META + 4

        CommandStrip(self._footer_rect, self.buttons).draw(surface, app.virtual_mouse_pos())
