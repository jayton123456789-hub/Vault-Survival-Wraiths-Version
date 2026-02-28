from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_rows
from bit_life_survival.app.ui.modal import Modal, ModalButton
from bit_life_survival.app.ui.widgets import Button, Panel, SectionCard, draw_text, wrap_text

from .core import Scene


class NewGameScene(Scene):
    def __init__(self) -> None:
        self.slot_buttons: list[Button] = []
        self._slot_ids: tuple[int, ...] = (1, 2, 3)
        self.back_button: Button | None = None
        self.modal: Modal | None = None
        self.pending_slot: int | None = None
        self._last_size: tuple[int, int] | None = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._slot_cards: list[pygame.Rect] = []
        self._subtitle_rect = pygame.Rect(0, 0, 0, 0)

    def _layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.slot_buttons:
            return
        self._last_size = app.screen.get_size()
        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=940, min_h=600, max_w=1320, max_h=820)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._subtitle_rect, slots_rect, footer = split_rows(content, [0.12, 0.76, 0.12], gap=10)

        self._slot_ids = tuple(app.save_service.slot_ids)
        self._slot_cards = split_rows(slots_rect, [1 for _ in self._slot_ids], gap=10)
        self.slot_buttons = []
        for card, slot in zip(self._slot_cards, self._slot_ids):
            button_rect = pygame.Rect(card.left + 12, card.top + 30, min(230, card.width - 24), 36)
            self.slot_buttons.append(
                Button(
                    button_rect,
                    f"Slot {slot}",
                    on_click=lambda s=slot: self._select_slot(app, s),
                    allow_skin=False,
                    text_fit_mode="ellipsis",
                    max_font_role="section",
                    tooltip="Start new game in selected slot.",
                )
            )

        self.back_button = Button(
            pygame.Rect(footer.left, footer.top + 8, 220, footer.height - 10),
            "Back",
            hotkey=pygame.K_ESCAPE,
            on_click=lambda: self._go_back(app),
            skin_key="back",
            skin_render_mode="frame_text",
            max_font_role="section",
            tooltip="Return to main menu.",
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

    def _draw_slot_card(self, app, surface: pygame.Surface, slot: int, card: pygame.Rect, button: Button) -> None:
        summary = {entry.slot: entry for entry in app.save_service.list_slots()}[slot]
        body = SectionCard(card, f"Slot {slot}").draw(surface)
        badge_rect = pygame.Rect(card.right - 122, card.top + 4, 112, 22)
        badge_color = theme.COLOR_WARNING if summary.occupied else theme.COLOR_SUCCESS
        pygame.draw.rect(surface, badge_color, badge_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, badge_rect, width=1, border_radius=2)
        badge_text = "OCCUPIED" if summary.occupied else "EMPTY"
        draw_text(surface, badge_text, theme.get_font(12, bold=True, kind="display"), theme.COLOR_BG, badge_rect.center, "center")

        button.text = "Start New Protocol"
        button.draw(surface, app.virtual_mouse_pos())

        info_x = button.rect.right + 16
        y = body.top + 4
        if summary.occupied:
            details = [
                f"Vault Lv {summary.vault_level}  |  TAV {summary.tav}  |  Drone Bay {summary.drone_bay_level}",
                f"Distance {summary.last_distance:.1f} mi  |  Time {summary.last_time} ticks",
                "Overwriting starts a fresh vault progression.",
            ]
            colors = [theme.COLOR_TEXT, theme.COLOR_TEXT_MUTED, theme.COLOR_WARNING]
        else:
            details = [
                "No existing save data in this slot.",
                "Starting here creates a new vault campaign.",
            ]
            colors = [theme.COLOR_TEXT_MUTED, theme.COLOR_TEXT_MUTED]
        for line, color in zip(details, colors):
            for wrapped in wrap_text(line, theme.get_font(15), max(120, body.right - info_x)):
                draw_text(surface, wrapped, theme.get_font(15), color, (info_x, y))
                y += 18

    def render(self, app, surface: pygame.Surface) -> None:
        self._layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="New Game").draw(surface)

        subtitle = SectionCard(self._subtitle_rect, "Slot Selection").draw(surface)
        draw_text(surface, "Choose a slot and launch a new protocol.", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (subtitle.left, subtitle.top + 2))

        for slot, button, card in zip(self._slot_ids, self.slot_buttons, self._slot_cards):
            self._draw_slot_card(app, surface, slot, card, button)

        if self.back_button:
            self.back_button.draw(surface, app.virtual_mouse_pos())

        if self.modal:
            self.modal.draw(surface)
