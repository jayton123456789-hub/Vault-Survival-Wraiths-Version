from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_columns
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text, wrap_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


BIOME_BRIEF = {
    "suburbs": "Collapsed streets, dead power lines, and contested scav routes. Visibility is fair, but ambushes are common.",
    "forest": "Dense tree cover and wet ground. Slow movement, limited visibility, frequent exposure hazards.",
    "industrial": "Steam vents, metal yards, and broken machinery. High injury risk, rich salvage pockets.",
}


class BriefingScene(Scene):
    def __init__(self, run_seed: int | str, biome_id: str = "suburbs") -> None:
        self.run_seed = run_seed
        self.biome_id = biome_id
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

    def _begin_run(self, app) -> None:
        from .run import RunScene

        app.change_scene(RunScene(run_seed=self.run_seed, biome_id=self.biome_id, auto_step_once=True))

    def _back(self, app) -> None:
        from .loadout import LoadoutScene

        app.change_scene(LoadoutScene())

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        panel = anchored_rect(app.screen.get_rect(), (1020, 620), "center")
        self._panel_rect = panel

        footer = pygame.Rect(panel.left + 20, panel.bottom - 56, panel.width - 40, 38)
        cols = split_columns(footer, [1, 1], gap=10)
        self.buttons.append(Button(cols[0], "Back to Loadout", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), tooltip="Return and adjust gear."))
        self.buttons.append(Button(cols[1], "Begin Run", hotkey=pygame.K_RETURN, on_click=lambda: self._begin_run(app), tooltip="Start mission and trigger first event."))

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
        Panel(self._panel_rect, title="Pre-Deploy Briefing").draw(surface)

        citizen = app.save_data.vault.current_citizen
        state = GameState(seed=self.run_seed, biome_id=self.biome_id, rng_state=1, rng_calls=0, equipped=app.current_loadout.model_copy(deep=True))
        summary = compute_loadout_summary(state, app.content)
        tags = ", ".join(summary["tags"]) if summary["tags"] else "None"

        left = pygame.Rect(self._panel_rect.left + 18, self._panel_rect.top + 52, int(self._panel_rect.width * 0.46), self._panel_rect.height - 130)
        right = pygame.Rect(left.right + 16, left.top, self._panel_rect.right - left.right - 34, left.height)

        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, left, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_BORDER, left, width=1, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, right, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_BORDER, right, width=1, border_radius=8)

        y = left.top + 14
        draw_text(surface, "Citizen", theme.get_font(20, bold=True), theme.COLOR_TEXT, (left.left + 12, y))
        y += 28
        if citizen:
            draw_text(surface, citizen.name, theme.get_font(24, bold=True), theme.COLOR_SUCCESS, (left.left + 12, y))
            y += 30
            draw_text(surface, f"Quirk: {citizen.quirk}", theme.get_font(16), theme.COLOR_TEXT_MUTED, (left.left + 12, y))
            y += 24
            kit_line = ", ".join(f"{item} x{qty}" for item, qty in sorted(citizen.kit.items())) or "None"
            for line in wrap_text(f"Kit: {kit_line}", theme.get_font(15), left.width - 24):
                draw_text(surface, line, theme.get_font(15), theme.COLOR_TEXT, (left.left + 12, y))
                y += 20
        else:
            draw_text(surface, "No drafted citizen.", theme.get_font(16), theme.COLOR_WARNING, (left.left + 12, y))
            y += 24

        y += 6
        draw_text(surface, "Equipped Loadout", theme.get_font(18, bold=True), theme.COLOR_TEXT, (left.left + 12, y))
        y += 24
        for slot_name, item_id in app.current_loadout.model_dump(mode="python").items():
            draw_text(surface, f"{slot_name}: {item_id or '-'}", theme.get_font(15), theme.COLOR_TEXT_MUTED, (left.left + 12, y))
            y += 20
        y += 6
        draw_text(surface, f"Tags: {tags}", theme.get_font(15), theme.COLOR_TEXT, (left.left + 12, y))

        y = right.top + 14
        draw_text(surface, "Mission Frame", theme.get_font(20, bold=True), theme.COLOR_TEXT, (right.left + 12, y))
        y += 30
        draw_text(surface, f"Biome: {self.biome_id.title()}", theme.get_font(18, bold=True), theme.COLOR_ACCENT, (right.left + 12, y))
        y += 26
        vibe = BIOME_BRIEF.get(self.biome_id, "Unknown territory. Stay adaptable.")
        for line in wrap_text(vibe, theme.get_font(16), right.width - 24):
            draw_text(surface, line, theme.get_font(16), theme.COLOR_TEXT_MUTED, (right.left + 12, y))
            y += 22
        y += 10
        draw_text(surface, "Likely Hazards", theme.get_font(18, bold=True), theme.COLOR_TEXT, (right.left + 12, y))
        y += 24
        hazard_lines = [
            "- Hydration loss spikes during long pushes.",
            "- Injury compounds morale decay.",
            "- Tag-locked options can avoid major losses.",
        ]
        if "Toxic" not in summary["tags"]:
            hazard_lines.append("- No Toxic gear equipped: chemical routes are riskier.")
        if "Medical" not in summary["tags"]:
            hazard_lines.append("- No Medical tag: fewer treatment options.")
        for line in hazard_lines:
            for wrapped in wrap_text(line, theme.get_font(15), right.width - 24):
                draw_text(surface, wrapped, theme.get_font(15), theme.COLOR_TEXT_MUTED, (right.left + 12, y))
                y += 20

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)
