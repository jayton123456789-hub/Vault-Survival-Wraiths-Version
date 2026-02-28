from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, CommandStrip, Panel, SectionCard, StatChip, draw_text, wrap_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import get_active_deploy_citizen
from bit_life_survival.core.rng import DeterministicRNG
from bit_life_survival.core.run_director import EXTRACTION_MILESTONES, next_extraction_target, snapshot as director_snapshot
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


BIOME_BRIEF = {
    "suburbs": "Collapsed streets and contested salvage routes. Visibility is moderate, ambush risk is high.",
    "forest": "Dense cover with wet ground. Movement slows and hydration pressure increases over time.",
    "industrial": "Heavy machinery zones with high injury risk and concentrated scrap opportunities.",
}


class BriefingScene(Scene):
    def __init__(self, run_seed: int | str, biome_id: str | None = None) -> None:
        self.run_seed = run_seed
        self.biome_id = biome_id
        self._resolved_biome_id: str | None = None
        self.buttons: list[Button] = []
        self._route_buttons: dict[str, Button] = {}
        self._last_size: tuple[int, int] | None = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._cards_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)

    def _resolve_biome(self, app) -> str:
        if self._resolved_biome_id:
            return self._resolved_biome_id
        if self.biome_id and self.biome_id in app.content.biome_by_id:
            self._resolved_biome_id = self.biome_id
            return self._resolved_biome_id
        biome_ids = sorted(app.content.biome_by_id.keys())
        if not biome_ids:
            self._resolved_biome_id = "suburbs"
            return self._resolved_biome_id
        rng = DeterministicRNG.from_seed(f"{self.run_seed}:briefing_biome")
        self._resolved_biome_id = biome_ids[rng.next_int(0, len(biome_ids))]
        return self._resolved_biome_id

    def _set_biome(self, biome_id: str) -> None:
        self._resolved_biome_id = biome_id

    def _begin_run(self, app) -> None:
        from .run import RunScene

        biome_id = self._resolve_biome(app)
        app.change_scene(RunScene(run_seed=self.run_seed, biome_id=biome_id, auto_step_once=True))

    def _back(self, app) -> None:
        from .operations import OperationsScene

        app.change_scene(OperationsScene(initial_tab="loadout"))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._route_buttons.clear()

        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=980, min_h=620, max_w=1420, max_h=860)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._cards_rect, self._footer_rect = split_rows(content, [0.84, 0.16], gap=10)
        top_cards, _ = split_rows(self._cards_rect, [0.5, 0.5], gap=10)
        upper = split_columns(top_cards, [1, 1], gap=10)
        route_rect = upper[1]
        route_button_row = pygame.Rect(route_rect.left + 12, route_rect.bottom - 42, route_rect.width - 24, 28)
        biome_ids = sorted(app.content.biome_by_id.keys())
        if biome_ids:
            cols = split_columns(route_button_row, [1 for _ in biome_ids], gap=6)
            for rect, biome_id in zip(cols, biome_ids):
                button = Button(
                    rect,
                    biome_id.title(),
                    on_click=lambda bid=biome_id: self._set_biome(bid),
                    allow_skin=False,
                    max_font_role="meta",
                    tooltip=f"Set route biome to {biome_id}.",
                )
                self._route_buttons[biome_id] = button
                self.buttons.append(button)
        footer_cols = split_columns(pygame.Rect(self._footer_rect.left + 2, self._footer_rect.top + 6, self._footer_rect.width - 4, self._footer_rect.height - 8), [1, 1], gap=10)
        self.buttons = [
            *self.buttons,
            Button(footer_cols[0], "Back to Operations", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), skin_key="loadout", skin_render_mode="frame_text", max_font_role="section", tooltip="Return and adjust loadout."),
            Button(footer_cols[1], "Begin Run", hotkey=pygame.K_RETURN, on_click=lambda: self._begin_run(app), skin_key="deploy", skin_render_mode="frame_text", max_font_role="section", tooltip="Start mission and proceed to run."),
        ]

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        for button in self.buttons:
            if button.handle_event(event):
                return

    def _draw_operator_card(self, app, surface: pygame.Surface, rect: pygame.Rect, summary: dict[str, float | list[str]]) -> None:
        body = SectionCard(rect, "Operator").draw(surface)
        citizen = get_active_deploy_citizen(app.save_data.vault)
        y = body.top
        if citizen:
            draw_text(surface, citizen.name, theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_SUCCESS, (body.left, y))
            y += 28
            draw_text(surface, f"Quirk: {citizen.quirk}", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (body.left, y))
            y += 24
            kit_line = ", ".join(f"{item} x{qty}" for item, qty in sorted(citizen.kit.items())) or "No kit"
            for line in wrap_text(f"Kit: {kit_line}", theme.get_role_font("meta"), body.width):
                draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT, (body.left, y))
                y += theme.FONT_SIZE_META + 4
        else:
            draw_text(surface, "No drafted citizen selected.", theme.get_role_font("body"), theme.COLOR_WARNING, (body.left, y))
            y += 24
        y += 6
        chips = split_columns(pygame.Rect(body.left, y, body.width, 28), [1, 1, 1], gap=6)
        StatChip(chips[0], "Speed", f"{float(summary['speed_bonus']):+.2f}").draw(surface)
        StatChip(chips[1], "Carry", f"{float(summary['carry_bonus']):+.1f}").draw(surface)
        StatChip(chips[2], "InjuryRes", f"{float(summary['injury_resist']) * 100:.0f}%").draw(surface)

    def _draw_route_card(self, surface: pygame.Surface, rect: pygame.Rect, biome_id: str) -> None:
        body = SectionCard(rect, "Route / Biome").draw(surface)
        y = body.top
        draw_text(surface, biome_id.title(), theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_ACCENT, (body.left, y))
        y += 30
        for line in wrap_text(BIOME_BRIEF.get(biome_id, "Unknown territory. Stay adaptive."), theme.get_role_font("body"), body.width):
            draw_text(surface, line, theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (body.left, y))
            y += theme.FONT_SIZE_BODY + 4
        director = director_snapshot(0.0, 0, self.run_seed)
        y += 4
        draw_text(
            surface,
            f"Run Profile: {director.profile_name}",
            theme.get_role_font("meta", bold=True),
            theme.COLOR_TEXT,
            (body.left, y),
        )
        y += 18
        for line in wrap_text(director.profile_blurb, theme.get_role_font("meta"), body.width):
            draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (body.left, y))
            y += theme.FONT_SIZE_META + 3
        y += 8
        draw_text(surface, "Run seed", theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (body.left, y))
        y += 18
        draw_text(surface, str(self.run_seed), theme.get_role_font("body", bold=True), theme.COLOR_TEXT, (body.left, y))

    def _draw_threat_card(self, surface: pygame.Surface, rect: pygame.Rect, tags: str, reward_band: str, extraction_target: float) -> None:
        body = SectionCard(rect, "Mission Outlook").draw(surface)
        y = body.top
        director_safe = director_snapshot(EXTRACTION_MILESTONES[0], int(EXTRACTION_MILESTONES[0]), self.run_seed)
        director_risk = director_snapshot(EXTRACTION_MILESTONES[1], int(EXTRACTION_MILESTONES[1]), self.run_seed)
        director_deep = director_snapshot(EXTRACTION_MILESTONES[2], int(EXTRACTION_MILESTONES[2]), self.run_seed)
        lines = [
            "Objective: reach a checkpoint, then choose push or extract.",
            "Main Risk: hydration collapse and injury spikes.",
            f"Reward Band: {reward_band}",
            f"First extraction target: {extraction_target:.1f} mi",
            f"Safe Push {EXTRACTION_MILESTONES[0]:.0f} mi -> x{director_safe.reward_multiplier:.2f}",
            f"Risk Push {EXTRACTION_MILESTONES[1]:.0f} mi -> x{director_risk.reward_multiplier:.2f}",
            f"Deep Push {EXTRACTION_MILESTONES[2]:.0f} mi -> x{director_deep.reward_multiplier:.2f}",
            "Recommended Prep: survivability + one utility tag.",
            f"Active tags: {tags or '-'}",
        ]
        for line in lines:
            for wrapped in wrap_text(line, theme.get_role_font("meta"), body.width):
                color = theme.COLOR_TEXT if line.startswith("Active tags") else theme.COLOR_TEXT_MUTED
                draw_text(surface, wrapped, theme.get_role_font("meta"), color, (body.left, y))
                y += theme.FONT_SIZE_META + 4

    def _draw_readiness_card(self, app, surface: pygame.Surface, rect: pygame.Rect) -> None:
        body = SectionCard(rect, "Equipment Readiness").draw(surface)
        y = body.top
        slots = app.current_loadout.model_dump(mode="python")
        filled = 0
        for slot_name, item_id in slots.items():
            if item_id:
                filled += 1
            if item_id and item_id in app.content.item_by_id:
                item_label = app.content.item_by_id[item_id].name
            else:
                item_label = item_id or "-"
            label = f"{slot_name}: {item_label}"
            draw_text(
                surface,
                label[:44] if len(label) > 44 else label,
                theme.get_role_font("meta"),
                theme.COLOR_TEXT if item_id else theme.COLOR_TEXT_MUTED,
                (body.left, y),
            )
            y += theme.FONT_SIZE_META + 4
        readiness = int((filled / max(1, len(slots))) * 100)
        y += 6
        draw_text(surface, f"Readiness {readiness}%", theme.get_role_font("section", bold=True, kind="display"), theme.COLOR_SUCCESS if readiness >= 60 else theme.COLOR_WARNING, (body.left, y))

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Mission Briefing").draw(surface)

        biome_id = self._resolve_biome(app)
        for key, button in self._route_buttons.items():
            if key == biome_id:
                button.bg = theme.COLOR_ACCENT_SOFT
                button.bg_hover = theme.COLOR_ACCENT
            else:
                button.bg = theme.COLOR_PANEL_ALT
                button.bg_hover = theme.COLOR_ACCENT_SOFT
        state = GameState(seed=self.run_seed, biome_id=biome_id, rng_state=1, rng_calls=0, equipped=app.current_loadout.model_copy(deep=True))
        summary = compute_loadout_summary(state, app.content)
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        start_director = director_snapshot(0.0, 0, self.run_seed)
        late_director = director_snapshot(40.0, 40, self.run_seed)
        reward_band = f"x{start_director.reward_multiplier:.2f} to x{late_director.reward_multiplier:.2f}"
        extraction_target = next_extraction_target(0.0)

        top_cards, bottom_cards = split_rows(self._cards_rect, [0.5, 0.5], gap=10)
        upper = split_columns(top_cards, [1, 1], gap=10)
        lower = split_columns(bottom_cards, [1, 1], gap=10)

        self._draw_operator_card(app, surface, upper[0], summary)
        self._draw_route_card(surface, upper[1], biome_id)
        self._draw_threat_card(surface, lower[0], tags, reward_band, extraction_target)
        self._draw_readiness_card(app, surface, lower[1])

        mouse_pos = app.virtual_mouse_pos()
        for button in self._route_buttons.values():
            button.draw(surface, mouse_pos)

        footer_buttons = [button for button in self.buttons if button not in self._route_buttons.values()]
        CommandStrip(self._footer_rect, footer_buttons).draw(surface, mouse_pos)
