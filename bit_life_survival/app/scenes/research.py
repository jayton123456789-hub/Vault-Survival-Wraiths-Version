from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, StatChip, draw_text, wrap_text
from bit_life_survival.core.research import (
    RESEARCH_NODES,
    NODE_BY_ID,
    buy_research,
    campaign_progress,
    can_research,
    contracts_unlocked,
    next_level_cost,
    research_level,
)

from .core import Scene


class ResearchScene(Scene):
    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self._node_buttons: dict[str, Button] = {}
        self._last_size: tuple[int, int] | None = None
        self.message = ""
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._body_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _back(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _buy(self, app, node_id: str) -> None:
        try:
            cost = buy_research(app.save_data.vault, node_id)
        except ValueError as exc:
            self.message = str(exc)
            return
        app.save_current_slot()
        self.message = f"{NODE_BY_ID[node_id].name} upgraded for {cost} scrap."
        self._last_size = None

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._node_buttons.clear()

        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=1100, min_h=680, max_w=1560, max_h=920)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        top_rect, self._body_rect, self._footer_rect = split_rows(content, [0.10, 0.76, 0.14], gap=10)

        top_chips = split_columns(pygame.Rect(top_rect.left, top_rect.top, top_rect.width, top_rect.height), [1, 1, 1, 1], gap=8)
        self._top_chip_rects = top_chips

        branches = ["Survival", "Salvage/Mobility", "Population/Infrastructure", "Drone Engineering", "Command/Operations"]
        branch_cols = split_columns(self._body_rect, [1, 1, 1, 1, 1], gap=8)
        grouped = {branch: [node for node in RESEARCH_NODES if node.branch == branch] for branch in branches}
        for rect, branch in zip(branch_cols, branches):
            body = pygame.Rect(rect.left + 10, rect.top + 34, rect.width - 20, rect.height - 44)
            row_height = 54
            for idx, node in enumerate(grouped[branch]):
                row = pygame.Rect(body.left, body.top + (idx * row_height), body.width, 30)
                button = Button(
                    row,
                    node.name,
                    on_click=lambda node_id=node.id: self._buy(app, node_id),
                    allow_skin=False,
                    max_font_role="meta",
                    tooltip=node.description,
                )
                self._node_buttons[node.id] = button
                self.buttons.append(button)

        footer_cols = split_columns(pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8), [1, 1], gap=10)
        self.buttons.extend(
            [
                Button(footer_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), skin_key="main_menu", skin_render_mode="frame_text", max_font_role="section"),
                Button(footer_cols[1], "Return to Base", hotkey=pygame.K_b, on_click=lambda: self._back(app), skin_key="deploy", skin_render_mode="frame_text", max_font_role="section"),
            ]
        )

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
        Panel(self._panel_rect, title="Research Command").draw(surface)
        vault = app.save_data.vault

        StatChip(self._top_chip_rects[0], "Scrap", str(int(vault.materials.get("scrap", 0)))).draw(surface)
        StatChip(self._top_chip_rects[1], "TAV", str(int(vault.tav))).draw(surface)
        StatChip(self._top_chip_rects[2], "Contracts", "Online" if contracts_unlocked(vault) else "Locked").draw(surface)
        StatChip(self._top_chip_rects[3], "Campaign", f"{int(round(campaign_progress(vault) * 100))}%").draw(surface)

        branches = ["Survival", "Salvage/Mobility", "Population/Infrastructure", "Drone Engineering", "Command/Operations"]
        branch_cols = split_columns(self._body_rect, [1, 1, 1, 1, 1], gap=8)
        for rect, branch in zip(branch_cols, branches):
            body = SectionCard(rect, branch).draw(surface)
            nodes = [node for node in RESEARCH_NODES if node.branch == branch]
            y = body.top
            for node in nodes:
                button = self._node_buttons[node.id]
                level = research_level(vault, node.id)
                cost = next_level_cost(vault, node.id)
                ok, reason = can_research(vault, node.id)
                button.rect = pygame.Rect(body.left, y, body.width, 30)
                button.text = f"{node.name} Lv {level}/{node.max_level}"
                button.enabled = cost is not None and ok
                button.draw(surface, app.virtual_mouse_pos())
                y += 34
                color = theme.COLOR_TEXT if ok else theme.COLOR_TEXT_MUTED
                subtitle = f"Cost {cost} scrap" if cost is not None else "Maxed"
                if not ok and cost is not None:
                    subtitle = reason
                for line in wrap_text(f"{subtitle}. {node.description}", theme.get_role_font("meta"), body.width):
                    draw_text(surface, line, theme.get_role_font("meta"), color, (body.left, y))
                    y += theme.FONT_SIZE_META + 2
                if node.requires:
                    deps = ", ".join(NODE_BY_ID[dep].name for dep in node.requires)
                    draw_text(surface, f"Requires: {deps}", theme.get_role_font("meta"), theme.COLOR_WARNING, (body.left, y))
                    y += theme.FONT_SIZE_META + 3
                y += 8

        footer_buttons = self.buttons[-2:]
        CommandStrip(self._footer_rect, footer_buttons).draw(surface, app.virtual_mouse_pos())
        if self.message:
            draw_text(surface, self.message, theme.get_role_font("body", bold=True), theme.COLOR_WARNING, (self._footer_rect.left + 8, self._footer_rect.top - 8), "bottomleft")
