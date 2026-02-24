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

    def _layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.slot_buttons:
            return
        self._last_size = app.screen.get_size()
        panel_rect = anchored_rect(app.screen.get_rect(), (820, 560))
        self._slot_ids = tuple(app.save_service.slot_ids)
        rows = split_rows(
            pygame.Rect(panel_rect.left + 20, panel_rect.top + 80, panel_rect.width - 40, panel_rect.height - 140),
            [1 for _ in self._slot_ids],
            gap=12,
        )
        self.slot_buttons = []
        for row, slot in zip(rows, self._slot_ids):
            self.slot_buttons.append(Button(row, f"Slot {slot}", on_click=lambda s=slot: self._select_slot(app, s)))
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
        surface.fill(theme.COLOR_BG)
        panel_rect = anchored_rect(surface.get_rect(), (820, 560))
        Panel(panel_rect, title="New Game - Choose Slot").draw(surface)

        summaries = {summary.slot: summary for summary in app.save_service.list_slots()}
        mouse_pos = app.virtual_mouse_pos()
        for slot, button in zip(self._slot_ids, self.slot_buttons):
            summary = summaries[slot]
            label = f"Slot {slot} - {'Occupied' if summary.occupied else 'Empty'}"
            button.text = label
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
            "Select a slot to start a new game.",
            theme.get_font(18),
            theme.COLOR_TEXT_MUTED,
            (panel_rect.left + 20, panel_rect.top + 48),
        )

        if self.modal:
            self.modal.draw(surface)
