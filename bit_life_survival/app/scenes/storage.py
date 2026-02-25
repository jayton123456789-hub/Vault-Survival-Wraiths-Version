from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text, wrap_text

from .core import Scene


SLOT_FILTER_VALUES = ["all", "pack", "armor", "vehicle", "utility", "faction", "consumable"]
RARITY_FILTER_VALUES = ["all", "common", "uncommon", "rare", "legendary"]
MATERIAL_IDS = ("scrap", "cloth", "plastic", "metal")


class StorageScene(Scene):
    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.selected_slot_filter = "all"
        self.selected_rarity_filter = "all"
        self.selected_item_id: str | None = None
        self._rows: list[tuple[str, int]] = []
        self.scroll: ScrollList | None = None

        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)
        self._list_rect = pygame.Rect(0, 0, 0, 0)
        self._detail_rect = pygame.Rect(0, 0, 0, 0)

    def _item_matches_filters(self, item) -> bool:
        if self.selected_slot_filter != "all" and item.slot != self.selected_slot_filter:
            return False
        if self.selected_rarity_filter != "all" and item.rarity != self.selected_rarity_filter:
            return False
        return True

    def _refresh_rows(self, app) -> None:
        rows: list[tuple[str, int]] = []
        for item_id, qty in sorted(app.save_data.vault.storage.items()):
            if qty <= 0:
                continue
            item = app.content.item_by_id.get(item_id)
            if not item or not self._item_matches_filters(item):
                continue
            rows.append((item_id, qty))
        self._rows = rows
        if self.scroll:
            lines = [f"{app.content.item_by_id[item_id].name}  x{qty}" for item_id, qty in rows]
            self.scroll.set_items(lines)
        if self.selected_item_id not in {item_id for item_id, _ in rows}:
            self.selected_item_id = rows[0][0] if rows else None

    def _on_select(self, index: int) -> None:
        if 0 <= index < len(self._rows):
            self.selected_item_id = self._rows[index][0]

    def _cycle_filter(self, app, which: str) -> None:
        if which == "slot":
            values = SLOT_FILTER_VALUES
            idx = values.index(self.selected_slot_filter)
            self.selected_slot_filter = values[(idx + 1) % len(values)]
        else:
            values = RARITY_FILTER_VALUES
            idx = values.index(self.selected_rarity_filter)
            self.selected_rarity_filter = values[(idx + 1) % len(values)]
        self._refresh_rows(app)

    def _back(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []

        panel = app.screen.get_rect().inflate(-18, -18)
        self._panel_rect = panel
        content = pygame.Rect(panel.left + 12, panel.top + 36, panel.width - 24, panel.height - 48)
        top, body, footer = split_rows(content, [0.17, 0.73, 0.10], gap=8)
        self._materials_rect = top
        list_rect, detail_rect = split_columns(body, [0.62, 0.38], gap=8)
        self._list_rect, self._detail_rect = list_rect, detail_rect

        filter_row = pygame.Rect(list_rect.left, list_rect.top, list_rect.width, 40)
        filter_cols = split_columns(filter_row, [1, 1], gap=8)
        self.buttons.append(Button(filter_cols[0], f"Slot: {self.selected_slot_filter}", on_click=lambda: self._cycle_filter(app, "slot"), tooltip="Cycle slot filter."))
        self.buttons.append(Button(filter_cols[1], f"Rarity: {self.selected_rarity_filter}", on_click=lambda: self._cycle_filter(app, "rarity"), tooltip="Cycle rarity filter."))

        list_inner = pygame.Rect(list_rect.left, list_rect.top + 48, list_rect.width, list_rect.height - 48)
        self.scroll = ScrollList(list_inner, row_height=30, on_select=self._on_select)
        self._refresh_rows(app)

        footer_cols = split_columns(footer, [1, 1], gap=8)
        self.buttons.append(Button(footer_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), tooltip="Return to base."))
        self.buttons.append(Button(footer_cols[1], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app), tooltip="Jump to loadout scene."))

    def _open_loadout(self, app) -> None:
        from .loadout import LoadoutScene

        app.change_scene(LoadoutScene())

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if self.scroll and self.scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_materials(self, app, surface: pygame.Surface) -> None:
        draw_text(surface, "Materials Pouch (does not consume storage capacity)", theme.get_font(15, bold=True), theme.COLOR_TEXT, (self._materials_rect.left + 2, self._materials_rect.top + 2))
        row = pygame.Rect(self._materials_rect.left, self._materials_rect.top + 22, self._materials_rect.width, self._materials_rect.height - 22)
        cols = split_columns(row, [1, 1, 1, 1], gap=8)
        for col, material_id in zip(cols, MATERIAL_IDS):
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=2, border_radius=2)
            qty = int(app.save_data.vault.materials.get(material_id, 0))
            draw_text(surface, f"{material_id.title()}  {qty}", theme.get_font(16, bold=True), theme.COLOR_TEXT, col.center, "center")

    def _draw_detail(self, app, surface: pygame.Surface) -> None:
        Panel(self._detail_rect, title="Item Details").draw(surface)
        if not self.selected_item_id:
            draw_text(surface, "No item selected.", theme.get_font(15), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 12, self._detail_rect.top + 50))
            return
        item = app.content.item_by_id.get(self.selected_item_id)
        if not item:
            draw_text(surface, "Item data missing.", theme.get_font(15), theme.COLOR_WARNING, (self._detail_rect.left + 12, self._detail_rect.top + 50))
            return
        y = self._detail_rect.top + 50
        draw_text(surface, item.name, theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._detail_rect.left + 12, y))
        y += 24
        draw_text(surface, f"{item.rarity} | {item.slot}", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 12, y))
        y += 20
        tags = ", ".join(item.tags) if item.tags else "-"
        for line in wrap_text(f"Tags: {tags}", theme.get_font(14), self._detail_rect.width - 24):
            draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT, (self._detail_rect.left + 12, y))
            y += 18
        y += 6
        mods = item.modifiers.model_dump(mode="python", exclude_none=True)
        if not mods:
            draw_text(surface, "No modifiers.", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 12, y))
            return
        for key, value in mods.items():
            if isinstance(value, float):
                text = f"{key}: {value:+.2f}"
            else:
                text = f"{key}: {value}"
            draw_text(surface, text, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 12, y))
            y += 18

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Storage").draw(surface)
        self._draw_materials(app, surface)
        Panel(self._list_rect, title="Gear Storage").draw(surface)
        if self.scroll:
            self.scroll.draw(surface)
        self._draw_detail(app, surface)
        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)
