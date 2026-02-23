from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import store_item, take_item
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


RUN_SLOTS = ("pack", "armor", "vehicle", "utility1", "utility2", "faction")
SLOT_FILTER_VALUES = ["all", "pack", "armor", "vehicle", "utility", "faction"]
RARITY_FILTER_VALUES = ["all", "common", "uncommon", "rare", "legendary"]


class LoadoutScene(Scene):
    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self.scroll_list: ScrollList | None = None
        self.selected_item_id: str | None = None
        self.selected_slot_filter = "all"
        self.selected_rarity_filter = "all"
        self.message = ""
        self._last_size: tuple[int, int] | None = None
        self._inventory_items: list[tuple[str, int]] = []

    def _allowed_slot(self, run_slot: str) -> str:
        return "utility" if run_slot in {"utility1", "utility2"} else run_slot

    def _item_matches_filter(self, item) -> bool:
        if self.selected_slot_filter != "all" and item.slot != self.selected_slot_filter:
            return False
        if self.selected_rarity_filter != "all" and item.rarity != self.selected_rarity_filter:
            return False
        return True

    def _refresh_inventory(self, app) -> None:
        rows: list[tuple[str, int]] = []
        for item_id, qty in sorted(app.save_data.vault.storage.items()):
            if qty <= 0:
                continue
            item = app.content.item_by_id.get(item_id)
            if not item:
                continue
            if item.slot not in {"pack", "armor", "vehicle", "utility", "faction"}:
                continue
            if not self._item_matches_filter(item):
                continue
            rows.append((item_id, qty))
        self._inventory_items = rows
        if self.scroll_list:
            self.scroll_list.set_items([f"{item_id} x{qty}" for item_id, qty in rows])

    def _cycle_filter(self, app, which: str) -> None:
        if which == "slot":
            values = SLOT_FILTER_VALUES
            idx = values.index(self.selected_slot_filter)
            self.selected_slot_filter = values[(idx + 1) % len(values)]
        else:
            values = RARITY_FILTER_VALUES
            idx = values.index(self.selected_rarity_filter)
            self.selected_rarity_filter = values[(idx + 1) % len(values)]
        self._refresh_inventory(app)

    def _on_select_inventory(self, index: int) -> None:
        if 0 <= index < len(self._inventory_items):
            self.selected_item_id = self._inventory_items[index][0]

    def _equip_to_slot(self, app, run_slot: str) -> None:
        if self.selected_item_id is None:
            self.message = "Select an item first."
            return
        item = app.content.item_by_id.get(self.selected_item_id)
        if not item:
            self.message = "Selected item no longer available."
            return
        if item.slot != self._allowed_slot(run_slot):
            self.message = f"{item.id} cannot be equipped to {run_slot}."
            return
        if not take_item(app.save_data.vault, item.id, 1):
            self.message = f"{item.id} unavailable in storage."
            return
        current = getattr(app.current_loadout, run_slot)
        if current:
            store_item(app.save_data.vault, current, 1)
        setattr(app.current_loadout, run_slot, item.id)
        self.message = f"Equipped {item.id} to {run_slot}."
        app.save_current_slot()
        self._refresh_inventory(app)

    def _unequip_slot(self, app, run_slot: str) -> None:
        current = getattr(app.current_loadout, run_slot)
        if not current:
            self.message = f"{run_slot} already empty."
            return
        store_item(app.save_data.vault, current, 1)
        setattr(app.current_loadout, run_slot, None)
        self.message = f"Unequipped {current}."
        app.save_current_slot()
        self._refresh_inventory(app)

    def _deploy(self, app) -> None:
        if app.save_data.vault.current_citizen is None:
            self.message = "Draft a citizen before deploying."
            return
        seed = app.compute_run_seed()
        app.save_data.vault.last_run_seed = seed
        app.save_data.vault.run_counter += 1
        app.save_current_slot()
        from .run import RunScene

        app.change_scene(RunScene(run_seed=seed))

    def _back(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons and self.scroll_list:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        root = app.screen.get_rect().inflate(-20, -20)
        rows = split_rows(root, [0.82, 0.18], gap=10)
        cols = split_columns(rows[0], [0.42, 0.58], gap=10)
        left = cols[0]
        right = cols[1]

        top_filters = pygame.Rect(left.left + 12, left.top + 42, left.width - 24, 38)
        filter_cols = split_columns(top_filters, [1, 1], gap=8)
        self.buttons.append(Button(filter_cols[0], f"Slot: {self.selected_slot_filter}", on_click=lambda: self._cycle_filter(app, "slot")))
        self.buttons.append(Button(filter_cols[1], f"Rarity: {self.selected_rarity_filter}", on_click=lambda: self._cycle_filter(app, "rarity")))

        list_rect = pygame.Rect(left.left + 12, left.top + 88, left.width - 24, left.height - 100)
        self.scroll_list = ScrollList(list_rect, row_height=30, on_select=self._on_select_inventory)
        self._refresh_inventory(app)

        slot_rows = [pygame.Rect(right.left + 12, right.top + 42 + i * 52, right.width - 24, 46) for i in range(len(RUN_SLOTS))]
        for slot_row, run_slot in zip(slot_rows, RUN_SLOTS):
            self.buttons.append(Button(slot_row, f"{run_slot}: -", on_click=lambda s=run_slot: self._equip_to_slot(app, s)))

        clear_row = pygame.Rect(right.left + 12, right.top + 42 + len(RUN_SLOTS) * 52, right.width - 24, 40)
        clear_cols = split_columns(clear_row, [1, 1, 1], gap=8)
        self.buttons.append(Button(clear_cols[0], "Clear Utility1", on_click=lambda: self._unequip_slot(app, "utility1")))
        self.buttons.append(Button(clear_cols[1], "Clear Utility2", on_click=lambda: self._unequip_slot(app, "utility2")))
        self.buttons.append(Button(clear_cols[2], "Clear Faction", on_click=lambda: self._unequip_slot(app, "faction")))

        bottom_cols = split_columns(pygame.Rect(rows[1].left + 8, rows[1].top + 8, rows[1].width - 16, rows[1].height - 16), [1, 1, 1], gap=10)
        self.buttons.append(Button(bottom_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app)))
        self.buttons.append(Button(bottom_cols[1], "Help", hotkey=pygame.K_h, on_click=lambda: self._show_help()))
        self.buttons.append(Button(bottom_cols[2], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app)))

        self._left_rect = left
        self._right_rect = right
        self._bottom_rect = rows[1]

    def _show_help(self) -> None:
        self.message = "Select inventory item -> click slot to equip. Filters cycle with top buttons."

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if self.scroll_list and self.scroll_list.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        surface.fill(theme.COLOR_BG)
        Panel(self._left_rect, title="Inventory").draw(surface)
        Panel(self._right_rect, title="Loadout").draw(surface)
        Panel(self._bottom_rect).draw(surface)
        mouse_pos = pygame.mouse.get_pos()

        for button in self.buttons:
            if button.text.startswith("pack:") or any(button.text.startswith(f"{slot}:") for slot in RUN_SLOTS):
                # Filled below after state snapshot.
                pass
            button.draw(surface, mouse_pos)
        if self.scroll_list:
            self.scroll_list.draw(surface)

        # Update slot button labels after drawing to keep references stable.
        slot_buttons = [button for button in self.buttons if any(button.text.startswith(f"{slot}:") for slot in RUN_SLOTS)]
        for button, run_slot in zip(slot_buttons, RUN_SLOTS):
            current = getattr(app.current_loadout, run_slot)
            button.text = f"{run_slot}: {current or '-'}"
            button.draw(surface, mouse_pos)

        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        y = self._right_rect.top + 430
        draw_text(surface, "Tags:", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 14, y))
        y += 22
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        draw_text(surface, tags, theme.get_font(15), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 14, y))
        y += 24
        carry_cap = 8 + max(0, int(round(summary["carry_bonus"])))
        lines = [
            f"Speed {summary['speed_bonus']:+.2f}",
            f"Carry Capacity {carry_cap}",
            f"Injury Resist {summary['injury_resist']*100:.0f}%",
            f"Stamina Mul {summary['stamina_mul']:.2f}",
            f"Hydration Mul {summary['hydration_mul']:.2f}",
        ]
        for line in lines:
            draw_text(surface, line, theme.get_font(15), theme.COLOR_TEXT, (self._right_rect.left + 14, y))
            y += 20

        if self.selected_item_id:
            draw_text(surface, f"Selected: {self.selected_item_id}", theme.get_font(16), theme.COLOR_ACCENT, (self._left_rect.left + 14, self._left_rect.bottom - 18), "midleft")
        if self.message:
            draw_text(surface, self.message, theme.get_font(17), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 8), "midbottom")
