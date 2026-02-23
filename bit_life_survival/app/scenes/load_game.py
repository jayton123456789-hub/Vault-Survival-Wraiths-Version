from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text

from .core import Scene


class LoadGameScene(Scene):
    def __init__(self) -> None:
        self.slot_buttons: list[Button] = []
        self.back_button: Button | None = None
        self._last_size: tuple[int, int] | None = None
        self.message: str = ""

    def _layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.slot_buttons:
            return
        self._last_size = app.screen.get_size()
        panel_rect = anchored_rect(app.screen.get_rect(), (820, 560))
        rows = split_rows(pygame.Rect(panel_rect.left + 20, panel_rect.top + 80, panel_rect.width - 40, panel_rect.height - 140), [1, 1, 1], gap=12)
        self.slot_buttons = []
        for row, slot in zip(rows, (1, 2, 3)):
            self.slot_buttons.append(Button(row, f"Slot {slot}", on_click=lambda s=slot: self._load_slot(app, s)))
        self.back_button = Button(
            pygame.Rect(panel_rect.left + 20, panel_rect.bottom - 48, 180, 34),
            "Back",
            hotkey=pygame.K_ESCAPE,
            on_click=lambda: self._go_back(app),
        )

    def _go_back(self, app) -> None:
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _load_slot(self, app, slot: int) -> None:
        if not app.save_service.slot_exists(slot):
            self.message = f"Slot {slot} is empty."
            return
        app.load_slot(slot)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._layout(app)
        if self.back_button and self.back_button.handle_event(event):
            return
        for button in self.slot_buttons:
            if button.handle_event(event):
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._layout(app)
        surface.fill(theme.COLOR_BG)
        panel_rect = anchored_rect(surface.get_rect(), (820, 560))
        Panel(panel_rect, title="Load Game").draw(surface)

        summaries = {summary.slot: summary for summary in app.save_service.list_slots()}
        mouse_pos = pygame.mouse.get_pos()
        for slot, button in zip((1, 2, 3), self.slot_buttons):
            summary = summaries[slot]
            button.text = f"Slot {slot} - {'Load' if summary.occupied else 'Empty'}"
            button.enabled = summary.occupied
            button.draw(surface, mouse_pos)
            subtitle = (
                f"Vault Lv {summary.vault_level} | TAV {summary.tav} | Drone {summary.drone_bay_level} | "
                f"Last {summary.last_distance:.1f} / t{summary.last_time}"
                if summary.occupied
                else "No save data"
            )
            draw_text(surface, subtitle, theme.get_font(15), theme.COLOR_TEXT_MUTED, (button.rect.left + 8, button.rect.bottom + 4))

        if self.back_button:
            self.back_button.draw(surface, mouse_pos)

        draw_text(
            surface,
            "Choose a slot to load.",
            theme.get_font(18),
            theme.COLOR_TEXT_MUTED,
            (panel_rect.left + 20, panel_rect.top + 48),
        )

        if self.message:
            draw_text(surface, self.message, theme.get_font(18), theme.COLOR_WARNING, (panel_rect.centerx, panel_rect.bottom - 18), "center")
