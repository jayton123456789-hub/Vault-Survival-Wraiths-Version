from __future__ import annotations

from datetime import datetime

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import anchored_rect, split_columns, split_rows
from bit_life_survival.app.ui.modal import Modal, ModalButton
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text, wrap_text

from .core import Scene


class MainMenuScene(Scene):
    def __init__(self, message: str = "") -> None:
        self.message = message
        self.buttons: list[Button] = []
        self.selected_slot: int = 1
        self.modal: Modal | None = None
        self.pending_action: tuple[str, int] | None = None
        self.rename_mode = False
        self.rename_text = ""
        self._last_size: tuple[int, int] | None = None
        self.slot_card_rects: dict[int, pygame.Rect] = {}

    def _summaries(self, app):
        return app.save_service.list_slots()

    def _summary_for_selected(self, app):
        summaries = self._summaries(app)
        summary = next((entry for entry in summaries if entry.slot == self.selected_slot), None)
        return summary or summaries[0]

    def _set_selected_slot(self, slot: int) -> None:
        self.selected_slot = slot
        self.rename_mode = False
        self.rename_text = ""

    def _continue(self, app) -> None:
        slot = app.save_service.last_slot()
        if slot is None or not app.save_service.slot_exists(slot):
            self.message = "No recent slot found."
            return
        app.load_slot(slot)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _load_selected(self, app) -> None:
        summary = self._summary_for_selected(app)
        if not summary.occupied:
            self.message = f"Slot {summary.slot} is empty."
            return
        app.load_slot(summary.slot)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _new_selected(self, app) -> None:
        summary = self._summary_for_selected(app)
        if summary.occupied:
            self.pending_action = ("new", summary.slot)
            self.modal = Modal(
                title="Overwrite Save Slot?",
                body_lines=[f"{summary.slot_name} has save data.", "Start new game and overwrite this slot?"],
                buttons=[
                    ModalButton("confirm", "Overwrite", hotkey=pygame.K_RETURN),
                    ModalButton("cancel", "Cancel", hotkey=pygame.K_ESCAPE),
                ],
            )
            return
        self._execute_new(app, summary.slot)

    def _execute_new(self, app, slot: int) -> None:
        base_seed = int(app.settings["gameplay"].get("base_seed", 1337))
        app.new_slot(slot, base_seed=base_seed)
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _delete_selected(self, app) -> None:
        summary = self._summary_for_selected(app)
        if not summary.occupied:
            self.message = "Selected slot is already empty."
            return
        self.pending_action = ("delete", summary.slot)
        self.modal = Modal(
            title="Delete Save Slot?",
            body_lines=[
                f"Delete {summary.slot_name} permanently?",
                "This cannot be undone.",
            ],
            buttons=[
                ModalButton("confirm", "Delete", hotkey=pygame.K_RETURN),
                ModalButton("cancel", "Cancel", hotkey=pygame.K_ESCAPE),
            ],
        )

    def _rename_selected(self, app) -> None:
        summary = self._summary_for_selected(app)
        self.rename_mode = True
        self.rename_text = summary.slot_name
        self.message = "Type a new slot name and press Enter."

    def _open_settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: MainMenuScene(message=self.message)))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self.slot_card_rects.clear()

        panel_rect = anchored_rect(app.screen.get_rect(), (1120, 640), "center")
        self._panel_rect = panel_rect
        cols = split_columns(pygame.Rect(panel_rect.left + 20, panel_rect.top + 58, panel_rect.width - 40, panel_rect.height - 130), [0.62, 0.38], gap=14)
        self._slots_rect = cols[0]
        self._actions_rect = cols[1]

        summaries = self._summaries(app)
        row_weights = [1.0 for _ in summaries]
        slot_rows = split_rows(self._slots_rect, row_weights, gap=10)
        for row, summary in zip(slot_rows, summaries):
            self.slot_card_rects[summary.slot] = row

        action_rows = split_rows(self._actions_rect, [1, 1, 1, 1, 1, 1, 1], gap=8)
        self.buttons.append(Button(action_rows[0], "Continue", hotkey=pygame.K_c, on_click=lambda: self._continue(app), tooltip="Load last played slot."))
        self.buttons.append(Button(action_rows[1], "New Game", hotkey=pygame.K_n, on_click=lambda: self._new_selected(app), tooltip="Create or overwrite selected slot."))
        self.buttons.append(Button(action_rows[2], "Load Slot", hotkey=pygame.K_l, on_click=lambda: self._load_selected(app), tooltip="Load selected slot."))
        self.buttons.append(Button(action_rows[3], "Rename Slot", hotkey=pygame.K_r, on_click=lambda: self._rename_selected(app), tooltip="Rename selected slot."))
        self.buttons.append(Button(action_rows[4], "Delete Slot", hotkey=pygame.K_DELETE, on_click=lambda: self._delete_selected(app), tooltip="Delete selected slot with confirmation."))
        self.buttons.append(Button(action_rows[5], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Open settings."))
        self.buttons.append(Button(action_rows[6], "Exit to Desktop", hotkey=pygame.K_ESCAPE, on_click=app.quit, tooltip="Quit game."))

        has_continue = app.save_service.last_slot() is not None and any(
            summary.slot == app.save_service.last_slot() and summary.occupied for summary in summaries
        )
        self.buttons[0].enabled = has_continue

    def _handle_modal(self, app, event: pygame.event.Event) -> bool:
        if not self.modal:
            return False
        result = self.modal.handle_event(event)
        if result == "confirm" and self.pending_action:
            action, slot = self.pending_action
            if action == "new":
                self._execute_new(app, slot)
            elif action == "delete":
                app.save_service.delete_slot(slot)
                self.message = f"Deleted slot {slot}."
                if self.selected_slot == slot:
                    self.selected_slot = 1
            self.modal = None
            self.pending_action = None
            self._last_size = None
        elif result in {"cancel", "close"}:
            self.modal = None
            self.pending_action = None
        return True

    def _handle_rename_input(self, app, event: pygame.event.Event) -> bool:
        if not self.rename_mode:
            return False
        if event.type != pygame.KEYDOWN:
            return True
        if event.key == pygame.K_ESCAPE:
            self.rename_mode = False
            self.message = "Rename cancelled."
            return True
        if event.key == pygame.K_RETURN:
            try:
                app.save_service.rename_slot(self.selected_slot, self.rename_text)
                self.message = f"Renamed slot {self.selected_slot}."
            except ValueError as exc:
                self.message = str(exc)
            self.rename_mode = False
            self._last_size = None
            return True
        if event.key == pygame.K_BACKSPACE:
            self.rename_text = self.rename_text[:-1]
            return True
        if event.unicode and len(self.rename_text) < 32 and event.unicode.isprintable():
            self.rename_text += event.unicode
            return True
        return True

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)

        if self._handle_modal(app, event):
            return
        if self._handle_rename_input(app, event):
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for slot, rect in self.slot_card_rects.items():
                if rect.collidepoint(event.pos):
                    self._set_selected_slot(slot)
                    return

        if event.type == pygame.KEYDOWN:
            summaries = self._summaries(app)
            slots = [entry.slot for entry in summaries]
            if event.key == pygame.K_UP:
                idx = max(0, slots.index(self.selected_slot) - 1) if self.selected_slot in slots else 0
                self._set_selected_slot(slots[idx])
                return
            if event.key == pygame.K_DOWN:
                idx = min(len(slots) - 1, slots.index(self.selected_slot) + 1) if self.selected_slot in slots else 0
                self._set_selected_slot(slots[idx])
                return

        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _format_timestamp(self, iso: str | None) -> str:
        if not iso:
            return "Never"
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return iso

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        surface.fill(theme.COLOR_BG)

        draw_text(surface, "Bit Life Survival", theme.get_font(54, bold=True), theme.COLOR_TEXT, (surface.get_width() // 2, 76), "center")
        draw_text(surface, "Vault Command Console", theme.get_font(20), theme.COLOR_TEXT_MUTED, (surface.get_width() // 2, 112), "center")

        Panel(self._panel_rect, title="Main Menu").draw(surface)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._slots_rect, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._slots_rect, width=1, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._actions_rect, border_radius=8)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._actions_rect, width=1, border_radius=8)

        summaries = self._summaries(app)
        for summary in summaries:
            rect = self.slot_card_rects[summary.slot]
            selected = summary.slot == self.selected_slot
            bg = theme.COLOR_ACCENT_SOFT if selected else (40, 46, 60)
            pygame.draw.rect(surface, bg, rect, border_radius=7)
            pygame.draw.rect(surface, theme.COLOR_BORDER, rect, width=1, border_radius=7)

            title = f"{summary.slot_name} ({'Occupied' if summary.occupied else 'Empty'})"
            draw_text(surface, title, theme.get_font(18, bold=True), theme.COLOR_TEXT, (rect.left + 12, rect.top + 10))
            if summary.occupied:
                details = [
                    f"Vault Lv {summary.vault_level}  |  TAV {summary.tav}  |  Drone {summary.drone_bay_level}",
                    f"Runs {summary.run_count}  |  Seed {summary.seed_preview}",
                    f"Last run: {summary.last_distance:.1f} mi / t{summary.last_time}",
                    f"Last played: {self._format_timestamp(summary.last_played)}",
                ]
            else:
                details = [
                    "No save data in this slot.",
                    f"Last played: {self._format_timestamp(summary.last_played)}",
                ]
            y = rect.top + 36
            for line in details:
                for wrapped in wrap_text(line, theme.get_font(14), rect.width - 24):
                    draw_text(surface, wrapped, theme.get_font(14), theme.COLOR_TEXT_MUTED, (rect.left + 12, y))
                    y += 16

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        if self.rename_mode:
            rename_rect = pygame.Rect(self._actions_rect.left, self._actions_rect.bottom + 8, self._actions_rect.width, 44)
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, rename_rect, border_radius=6)
            pygame.draw.rect(surface, theme.COLOR_BORDER, rename_rect, width=1, border_radius=6)
            draw_text(surface, f"Rename: {self.rename_text}_", theme.get_font(16), theme.COLOR_TEXT, (rename_rect.left + 10, rename_rect.centery), "midleft")

        if self.message:
            draw_text(surface, self.message, theme.get_font(18), theme.COLOR_WARNING, (surface.get_width() // 2, self._panel_rect.bottom + 18), "center")

        if self.modal:
            self.modal.draw(surface)
