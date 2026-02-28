from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect, scene_shell
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, StatChip, draw_text, wrap_text
from bit_life_survival.core.persistence import get_active_deploy_citizen, take_item

from .core import Scene


class DroneBayScene(Scene):
    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.message = ""
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._top_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._right_top_rect = pygame.Rect(0, 0, 0, 0)
        self._right_bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _back(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _open_operations(self, app) -> None:
        from .operations import OperationsScene

        app.change_scene(OperationsScene(initial_tab="loadout"))

    def _deploy(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault)
        if citizen is None:
            self.message = "No deploy-ready citizen selected."
            return
        from .briefing import BriefingScene

        seed = app.compute_run_seed()
        app.save_data.vault.last_run_seed = seed
        app.save_data.vault.run_counter += 1
        app.save_data.vault.current_citizen = citizen
        app.save_current_slot()
        app.change_scene(BriefingScene(run_seed=seed))

    def _upgrade_cost(self, level: int) -> dict[str, int]:
        return {"scrap": 8 + level * 5, "metal": 6 + level * 4, "plastic": 4 + level * 3}

    def _can_upgrade(self, app, level: int) -> tuple[bool, dict[str, tuple[int, int]]]:
        cost = self._upgrade_cost(level)
        reqs: dict[str, tuple[int, int]] = {}
        valid = True
        for item_id, required in cost.items():
            available = int(app.save_data.vault.materials.get(item_id, 0))
            reqs[item_id] = (available, required)
            if available < required:
                valid = False
        return valid, reqs

    def _do_upgrade(self, app) -> None:
        level = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
        if level >= 10:
            self.message = "Drone Bay is already at max level."
            return
        valid, reqs = self._can_upgrade(app, level)
        if not valid:
            self.message = "Missing materials for upgrade."
            return
        for item_id, (_, required) in reqs.items():
            take_item(app.save_data.vault, item_id, required)
        app.save_data.vault.upgrades["drone_bay_level"] = level + 1
        app.save_current_slot()
        self.message = f"Drone Bay upgraded to level {level + 1}."
        self._last_size = None

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []

        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1540, max_h=900)
        shell = pygame.Rect(self._panel_rect.left + 8, self._panel_rect.top + 30, self._panel_rect.width - 16, self._panel_rect.height - 36)
        self._top_rect, body, self._footer_rect = scene_shell(shell, top_ratio=0.18, footer_ratio=0.16, gap=10)
        self._left_rect, self._right_rect = split_columns(body, [0.58, 0.42], gap=10)
        self._right_top_rect, self._right_bottom_rect = split_rows(self._right_rect, [0.58, 0.42], gap=8)

        upgrade_button_rect = pygame.Rect(self._right_top_rect.left + 10, self._right_top_rect.bottom - 46, self._right_top_rect.width - 20, 36)
        self.buttons.append(
            Button(
                upgrade_button_rect,
                "Upgrade Drone Bay",
                on_click=lambda: self._do_upgrade(app),
                skin_key="drone_bay",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Spend materials to improve drone recovery reliability.",
            )
        )

        footer_cols = split_columns(
            pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8),
            [1, 1, 1],
            gap=10,
        )
        self.buttons.extend(
            [
                Button(
                    footer_cols[0],
                    "Back",
                    hotkey=pygame.K_ESCAPE,
                    on_click=lambda: self._back(app),
                    skin_key="back",
                    skin_render_mode="frame_text",
                    max_font_role="section",
                    tooltip="Return to Base.",
                ),
                Button(
                    footer_cols[1],
                    "Operations",
                    hotkey=pygame.K_o,
                    on_click=lambda: self._open_operations(app),
                    skin_key="loadout",
                    skin_render_mode="frame_text",
                    max_font_role="section",
                    tooltip="Open operations loadout.",
                ),
                Button(
                    footer_cols[2],
                    "Deploy",
                    hotkey=pygame.K_d,
                    on_click=lambda: self._deploy(app),
                    skin_key="deploy",
                    skin_render_mode="frame_text",
                    max_font_role="section",
                    tooltip="Launch selected operator.",
                ),
            ]
        )

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return

        # Ensure hit targets are current before button dispatch.
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "industrial")
        Panel(self._panel_rect, title="Drone Bay Command").draw(surface)

        level = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
        full_recovery = min(90, 42 + level * 6)
        partial_recovery = min(96, 24 + level * 4)
        loss_risk = max(2, 24 - level * 2)

        top_body = SectionCard(self._top_rect, "Recovery Status").draw(surface)
        chips = split_columns(pygame.Rect(top_body.left, top_body.top, top_body.width, 30), [1, 1, 1, 1], gap=8)
        StatChip(chips[0], "Bay Lv", str(level)).draw(surface)
        StatChip(chips[1], "TAV", str(app.save_data.vault.tav)).draw(surface)
        StatChip(chips[2], "Full Rec", f"{full_recovery}%").draw(surface)
        StatChip(chips[3], "Loss Risk", f"{loss_risk}%").draw(surface)

        left_body = SectionCard(self._left_rect, "Recovery Model").draw(surface)
        left_lines = [
            f"Full Recovery: ~{full_recovery}%",
            f"Partial Recovery: ~{partial_recovery}%",
            f"Loss Risk: ~{loss_risk}%",
            f"Runs completed: {app.save_data.vault.run_counter}",
            "Higher bay levels improve route reacquisition and salvage retention.",
        ]
        y = left_body.top
        for line in left_lines[:4]:
            draw_text(surface, line, theme.get_role_font("body"), theme.COLOR_TEXT, (left_body.left, y))
            y += theme.FONT_SIZE_BODY + 4
        y += 4
        for line in wrap_text(left_lines[4], theme.get_role_font("meta"), left_body.width):
            draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (left_body.left, y))
            y += theme.FONT_SIZE_META + 3

        right_top = SectionCard(self._right_top_rect, "Upgrade Cost").draw(surface)
        valid, reqs = self._can_upgrade(app, level)
        chip_rects = split_rows(
            pygame.Rect(right_top.left, right_top.top, right_top.width, min(96, right_top.height - 50)),
            [1, 1, 1],
            gap=6,
        )
        for rect, item_id in zip(chip_rects, ("scrap", "metal", "plastic")):
            available, required = reqs[item_id]
            tone = theme.COLOR_SUCCESS if available >= required else theme.COLOR_WARNING
            StatChip(rect, item_id.title(), f"{available}/{required}", tone=tone).draw(surface)
        status_line = "Upgrade ready" if valid else "Need more materials"
        draw_text(
            surface,
            status_line,
            theme.get_role_font("meta", bold=True, kind="display"),
            theme.COLOR_SUCCESS if valid else theme.COLOR_WARNING,
            (right_top.left, right_top.bottom - 6),
            "bottomleft",
        )

        right_bottom = SectionCard(self._right_bottom_rect, "Inspector").draw(surface)
        notes = [
            "Upgrades stack with run-distance value gains.",
            "Retreat still uses drone recovery, but with lower yield.",
            "Pair upgrades with loadout carry/resistance for stronger returns.",
        ]
        y = right_bottom.top
        for line in notes:
            for wrapped in wrap_text(line, theme.get_role_font("meta"), right_bottom.width):
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (right_bottom.left, y))
                y += theme.FONT_SIZE_META + 3
            y += 2

        CommandStrip(self._footer_rect, self.buttons[-3:]).draw(surface, app.virtual_mouse_pos())
        self.buttons[0].draw(surface, app.virtual_mouse_pos())

        if self.message:
            draw_text(surface, self.message, theme.get_role_font("body", bold=True), theme.COLOR_WARNING, (self._footer_rect.left + 8, self._footer_rect.top - 8), "bottomleft")
