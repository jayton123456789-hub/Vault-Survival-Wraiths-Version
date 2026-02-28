from __future__ import annotations

from datetime import datetime

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_rect
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, SectionCard, draw_text, wrap_text

from .core import Scene


class LoadGameScene(Scene):
    def __init__(self) -> None:
        self.slot_buttons: list[Button] = []
        self.delete_buttons: list[Button] = []
        self._slot_ids: tuple[int, ...] = (1, 2, 3)
        self.back_button: Button | None = None
        self._last_size: tuple[int, int] | None = None
        self.message: str = ""
        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._slot_cards: list[pygame.Rect] = []
        self._subtitle_rect = pygame.Rect(0, 0, 0, 0)
        self._pending_delete_slot: int | None = None

    @staticmethod
    def _fmt_ts(value: str | None) -> str:
        if not value:
            return "Never"
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.slot_buttons and self.delete_buttons:
            return
        self._last_size = app.screen.get_size()
        self._panel_rect = clamp_rect(app.screen.get_rect(), min_w=940, min_h=600, max_w=1320, max_h=820)
        content = pygame.Rect(self._panel_rect.left + 16, self._panel_rect.top + 36, self._panel_rect.width - 32, self._panel_rect.height - 52)
        self._subtitle_rect, slots_rect, footer = split_rows(content, [0.12, 0.76, 0.12], gap=10)

        self._slot_ids = tuple(app.save_service.slot_ids)
        self._slot_cards = split_rows(slots_rect, [1 for _ in self._slot_ids], gap=10)
        self.slot_buttons = []
        self.delete_buttons = []
        for card, slot in zip(self._slot_cards, self._slot_ids):
            button_row = pygame.Rect(card.left + 12, card.top + 30, min(470, card.width - 24), 36)
            load_rect, delete_rect = split_columns(button_row, [0.55, 0.45], gap=8)
            self.slot_buttons.append(
                Button(
                    load_rect,
                    "Load Slot",
                    on_click=lambda s=slot: self._load_slot(app, s),
                    skin_key="load_game",
                    skin_render_mode="frame_text",
                    text_fit_mode="ellipsis",
                    max_font_role="section",
                    tooltip="Load selected save slot.",
                )
            )
            self.delete_buttons.append(
                Button(
                    delete_rect,
                    "Delete Slot",
                    on_click=lambda s=slot: self._delete_slot(app, s),
                    skin_key="exit",
                    skin_render_mode="frame_text",
                    text_fit_mode="ellipsis",
                    max_font_role="section",
                    tooltip="Delete save data in this slot.",
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
        self._pending_delete_slot = None
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _load_slot(self, app, slot: int) -> None:
        self._pending_delete_slot = None
        if not app.save_service.slot_exists(slot):
            self.message = f"Slot {slot} is empty."
            return
        app.load_slot(slot)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _delete_slot(self, app, slot: int) -> None:
        if not app.save_service.slot_exists(slot):
            self._pending_delete_slot = None
            self.message = f"Slot {slot} is already empty."
            return
        if self._pending_delete_slot != slot:
            self._pending_delete_slot = slot
            self.message = f"Press Delete Slot again to confirm deletion for Slot {slot}."
            return
        app.save_service.delete_slot(slot)
        if getattr(app, "current_slot", None) == slot:
            app.current_slot = None
            app.save_data = None
        self._pending_delete_slot = None
        self.message = f"Deleted Slot {slot}."
        self._last_size = None

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._layout(app)
        if self.back_button and self.back_button.handle_event(event):
            return
        for load_button, delete_button in zip(self.slot_buttons, self.delete_buttons):
            if load_button.handle_event(event):
                return
            if delete_button.handle_event(event):
                return

    def _draw_slot_card(self, app, surface: pygame.Surface, slot: int, card: pygame.Rect, load_button: Button, delete_button: Button) -> None:
        summary_by_slot = {entry.slot: entry for entry in app.save_service.list_slots()}
        summary = summary_by_slot.get(slot)
        if summary is None:
            load_button.enabled = False
            delete_button.enabled = False
            return

        body = SectionCard(card, f"Slot {slot}").draw(surface)
        badge_rect = pygame.Rect(card.right - 128, card.top + 4, 118, 22)
        if summary.occupied:
            badge_color = theme.COLOR_ACCENT
            badge_text = "LAST PLAYED" if slot == app.save_service.last_slot() else "OCCUPIED"
        else:
            badge_color = theme.COLOR_PANEL_ALT
            badge_text = "EMPTY"
        pygame.draw.rect(surface, badge_color, badge_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, badge_rect, width=1, border_radius=2)
        draw_text(surface, badge_text, theme.get_font(11, bold=True, kind="display"), theme.COLOR_BG if summary.occupied else theme.COLOR_TEXT_MUTED, badge_rect.center, "center")

        load_button.enabled = summary.occupied
        load_button.text = "Load Slot"

        delete_button.enabled = summary.occupied
        if self._pending_delete_slot == slot and summary.occupied:
            delete_button.text = "Confirm Delete"
        else:
            delete_button.text = "Delete Slot"

        load_button.draw(surface, app.virtual_mouse_pos())
        delete_button.draw(surface, app.virtual_mouse_pos())

        info_x = max(load_button.rect.right, delete_button.rect.right) + 16
        y = body.top + 4
        if summary.occupied:
            lines = [
                f"Vault Lv {summary.vault_level}  |  TAV {summary.tav}  |  Drone Bay {summary.drone_bay_level}",
                f"Distance {summary.last_distance:.1f} mi  |  Time {summary.last_time} ticks",
                f"Last played {self._fmt_ts(summary.last_played)}",
            ]
            colors = [theme.COLOR_TEXT, theme.COLOR_TEXT_MUTED, theme.COLOR_TEXT_MUTED]
        else:
            lines = [
                "No save data in this slot.",
                "Create a new game from Main Menu > New Game.",
            ]
            colors = [theme.COLOR_TEXT_MUTED, theme.COLOR_TEXT_MUTED]
        for line, color in zip(lines, colors):
            for wrapped in wrap_text(line, theme.get_font(15), max(120, body.right - info_x)):
                draw_text(surface, wrapped, theme.get_font(15), color, (info_x, y))
                y += 18

    def render(self, app, surface: pygame.Surface) -> None:
        self._layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Load Game").draw(surface)

        subtitle = SectionCard(self._subtitle_rect, "Save Slots").draw(surface)
        draw_text(surface, "Select a slot to load or delete.", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (subtitle.left, subtitle.top + 2))

        for slot, load_button, delete_button, card in zip(self._slot_ids, self.slot_buttons, self.delete_buttons, self._slot_cards):
            self._draw_slot_card(app, surface, slot, card, load_button, delete_button)

        if self.back_button:
            self.back_button.draw(surface, app.virtual_mouse_pos())

        if self.message:
            draw_text(surface, self.message, theme.get_role_font("body", bold=True), theme.COLOR_WARNING, (self._panel_rect.centerx, self._panel_rect.bottom - 18), "center")
