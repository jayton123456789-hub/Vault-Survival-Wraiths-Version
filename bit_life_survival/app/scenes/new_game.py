from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_rows
from bit_life_survival.app.ui.modal import Modal, ModalButton
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text

from .core import Scene


class NewGameScene(Scene):
    def __init__(self) -> None:
        self.slot_buttons: list[Button] = []
        self._slot_ids: tuple[int, ...] = (1, 2, 3)
        self.back_button: Button | None = None
        self.modal: Modal | None = None
        self.pending_slot: int | None = None
        self._last_size: tuple[int, int] | None = None
        self._slot_cards: list[pygame.Rect] = []

    def _layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.slot_buttons:
            return
        self._last_size = app.screen.get_size()
        panel_rect = anchored_rect(app.screen.get_rect(), (900, 610))
        self._panel_rect = panel_rect
        self._slot_ids = tuple(app.save_service.slot_ids)
        rows = split_rows(
            pygame.Rect(panel_rect.left + 20, panel_rect.top + 90, panel_rect.width - 40, panel_rect.height - 160),
            [1 for _ in self._slot_ids],
            gap=10,
        )
        self.slot_buttons = []
        self._slot_cards = list(rows)
        for row, slot in zip(self._slot_cards, self._slot_ids):
            button_rect = pygame.Rect(row.left + 6, row.top + 6, row.width - 12, 44)
            self.slot_buttons.append(Button(button_rect, f"Slot {slot}", on_click=lambda s=slot: self._select_slot(app, s)))
        self.back_button = Button(
            pygame.Rect(panel_rect.left + 20, panel_rect.bottom - 48, 180, 34),
            "Back",
            hotkey=pygame.K_ESCAPE,
            on_click=lambda: self._go_back(app),
        )

    def _go_back(self, app) -> None:
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _select_slot(self, app, slot: int) -> None:
        if app.save_service.slot_exists(slot):
            self.pending_slot = slot
            self.modal = Modal(
                title="Overwrite Save Slot?",
                body_lines=[f"Slot {slot} already has data.", "Starting a new game will overwrite it."],
                buttons=[
                    ModalButton("confirm", "Overwrite", hotkey=pygame.K_RETURN),
                    ModalButton("cancel", "Cancel", hotkey=pygame.K_ESCAPE),
                ],
            )
            return
        self._start_new_game(app, slot)

    def _start_new_game(self, app, slot: int) -> None:
        base_seed = int(app.settings["gameplay"].get("base_seed", 1337))
        app.new_slot(slot, base_seed=base_seed)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return

        self._layout(app)
        if self.modal:
            result = self.modal.handle_event(event)
            if result == "confirm" and self.pending_slot is not None:
                slot = self.pending_slot
                self.modal = None
                self.pending_slot = None
                self._start_new_game(app, slot)
            elif result in {"cancel", "close"}:
                self.modal = None
                self.pending_slot = None
            return

        if self.back_button and self.back_button.handle_event(event):
            return
        for button in self.slot_buttons:
            if button.handle_event(event):
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._layout(app)
        app.backgrounds.draw(surface, "vault")
        panel_rect = self._panel_rect
        Panel(panel_rect, title="New Game - Choose Slot").draw(surface)

        summaries = {summary.slot: summary for summary in app.save_service.list_slots()}
        mouse_pos = app.virtual_mouse_pos()
        for slot, button, card in zip(self._slot_ids, self.slot_buttons, self._slot_cards):
            summary = summaries[slot]
            label = f"Slot {slot} - {'Occupied' if summary.occupied else 'Empty'}"
            button.text = label
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, card, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, card, width=2, border_radius=2)
            button.draw(surface, mouse_pos)
            if summary.occupied:
                line1 = f"Vault Lv {summary.vault_level} | TAV {summary.tav} | Drone {summary.drone_bay_level}"
                line2 = f"Last run {summary.last_distance:.1f} mi / t{summary.last_time}"
            else:
                line1 = "No save data"
                line2 = "Start fresh in this slot."
            draw_text(surface, line1, theme.get_font(13), theme.COLOR_TEXT_MUTED, (card.left + 10, card.top + 60))
            draw_text(surface, line2, theme.get_font(13), theme.COLOR_TEXT_MUTED, (card.left + 10, card.top + 76))

        if self.back_button:
            self.back_button.draw(surface, mouse_pos)

        draw_text(
            surface,
            "Select a slot to start a new game.",
            theme.get_font(18),
            theme.COLOR_TEXT_MUTED,
            (panel_rect.left + 20, panel_rect.top + 48),
        )

        if self.modal:
            self.modal.draw(surface)
