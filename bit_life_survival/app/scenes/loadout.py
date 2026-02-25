from __future__ import annotations

import pygame

from bit_life_survival.app.services.loadout_planner import RUN_SLOTS, choose_best_for_slot, format_choice_reason
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text, draw_tooltip_bar, hovered_tooltip, wrap_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import get_active_deploy_citizen, store_item, take_item
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


SLOT_FILTER_VALUES = ["all", "pack", "armor", "vehicle", "utility", "faction"]
RARITY_FILTER_VALUES = ["all", "common", "uncommon", "rare", "legendary"]


class LoadoutScene(Scene):
    def __init__(self) -> None:
        self.buttons: list[Button] = []
        self.scroll_list: ScrollList | None = None
        self.selected_item_id: str | None = None
        self.selected_slot_filter = "all"
        self.selected_rarity_filter = "all"
        self.active_slot: str | None = None
        self.message = ""
        self._last_size: tuple[int, int] | None = None
        self._inventory_items: list[tuple[str, int]] = []
        self._slot_buttons: dict[str, Button] = {}
        self.help_overlay = False

    def on_enter(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault) if app.save_data else None
        if citizen is not None:
            app.current_loadout = citizen.loadout.model_copy(deep=True)

    def _sync_citizen_loadout(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault) if app.save_data else None
        if citizen is not None:
            citizen.loadout = app.current_loadout.model_copy(deep=True)

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
            lines = []
            for item_id, qty in rows:
                item = app.content.item_by_id[item_id]
                lines.append(f"{item.name} ({item.rarity}) x{qty}")
            self.scroll_list.set_items(lines)

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

    def _equip_to_slot(self, app, run_slot: str) -> bool:
        self.active_slot = run_slot
        if self.selected_item_id is None:
            self.message = f"Selected slot: {run_slot}. Pick an item or use Equip Best."
            return False
        item = app.content.item_by_id.get(self.selected_item_id)
        if not item:
            self.message = "Selected item no longer available."
            return False
        if item.slot != self._allowed_slot(run_slot):
            self.message = f"{item.name} cannot be equipped to {run_slot}."
            return False
        if not take_item(app.save_data.vault, item.id, 1):
            self.message = f"{item.name} unavailable in storage."
            return False
        current = getattr(app.current_loadout, run_slot)
        if current:
            store_item(app.save_data.vault, current, 1)
        setattr(app.current_loadout, run_slot, item.id)
        self._sync_citizen_loadout(app)
        self.message = f"Equipped {item.name} to {run_slot}."
        app.save_current_slot()
        self._refresh_inventory(app)
        return True

    def _unequip_all(self, app) -> None:
        for run_slot in RUN_SLOTS:
            current = getattr(app.current_loadout, run_slot)
            if current:
                store_item(app.save_data.vault, current, 1)
                setattr(app.current_loadout, run_slot, None)

    def _equip_best_for_slot(self, app, run_slot: str) -> bool:
        current = getattr(app.current_loadout, run_slot)
        if current:
            store_item(app.save_data.vault, current, 1)
            setattr(app.current_loadout, run_slot, None)

        choice = choose_best_for_slot(app.content, app.save_data.vault.storage, run_slot, reserved={})
        if not choice:
            self.message = f"No compatible item for {run_slot}."
            return False
        if not take_item(app.save_data.vault, choice.item_id, 1):
            self.message = f"Unable to reserve {choice.item_id}."
            return False
        setattr(app.current_loadout, run_slot, choice.item_id)
        self._sync_citizen_loadout(app)
        self.message = format_choice_reason(app.content, choice)
        return True

    def _equip_best(self, app) -> None:
        if self.active_slot:
            self._equip_best_for_slot(app, self.active_slot)
        else:
            self._equip_all(app)
            return
        app.save_current_slot()
        self._refresh_inventory(app)

    def _equip_all(self, app) -> None:
        self._unequip_all(app)
        reserved: dict[str, int] = {}
        lines: list[str] = []
        for run_slot in RUN_SLOTS:
            choice = choose_best_for_slot(app.content, app.save_data.vault.storage, run_slot, reserved)
            if not choice:
                continue
            if not take_item(app.save_data.vault, choice.item_id, 1):
                continue
            reserved[choice.item_id] = reserved.get(choice.item_id, 0) + 1
            setattr(app.current_loadout, run_slot, choice.item_id)
            lines.append(format_choice_reason(app.content, choice))
        self._sync_citizen_loadout(app)
        app.save_current_slot()
        self._refresh_inventory(app)
        self.message = " ".join(lines[:2]) if lines else "No available gear to auto-equip."

    def _deploy(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault)
        if citizen is None:
            self.message = "Draft a citizen before deploying."
            return
        seed = app.compute_run_seed()
        app.save_data.vault.last_run_seed = seed
        app.save_data.vault.run_counter += 1
        app.save_data.vault.current_citizen = citizen
        self._sync_citizen_loadout(app)
        app.save_current_slot()
        from .briefing import BriefingScene

        app.change_scene(BriefingScene(run_seed=seed))

    def _back(self, app) -> None:
        from .base import BaseScene

        app.change_scene(BaseScene())

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons and self.scroll_list:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._slot_buttons.clear()
        root = app.screen.get_rect().inflate(-20, -20)
        rows = split_rows(root, [0.82, 0.18], gap=10)
        cols = split_columns(rows[0], [0.42, 0.58], gap=10)
        left = cols[0]
        right = cols[1]

        top_filters = pygame.Rect(left.left + 12, left.top + 42, left.width - 24, 38)
        filter_cols = split_columns(top_filters, [1, 1], gap=8)
        self.buttons.append(Button(filter_cols[0], f"Slot: {self.selected_slot_filter}", on_click=lambda: self._cycle_filter(app, "slot"), tooltip="Filter inventory by item slot."))
        self.buttons.append(Button(filter_cols[1], f"Rarity: {self.selected_rarity_filter}", on_click=lambda: self._cycle_filter(app, "rarity"), tooltip="Filter inventory by rarity tier."))

        list_rect = pygame.Rect(left.left + 12, left.top + 88, left.width - 24, left.height - 100)
        self.scroll_list = ScrollList(list_rect, row_height=30, on_select=self._on_select_inventory)
        self._refresh_inventory(app)

        slot_rows = [pygame.Rect(right.left + 12, right.top + 42 + i * 52, right.width - 24, 46) for i in range(len(RUN_SLOTS))]
        for slot_row, run_slot in zip(slot_rows, RUN_SLOTS):
            button = Button(
                slot_row,
                f"{run_slot}: -",
                on_click=lambda s=run_slot: self._equip_to_slot(app, s),
                tooltip=f"Equip selected item into {run_slot}. Click with no item to set active slot.",
            )
            self.buttons.append(button)
            self._slot_buttons[run_slot] = button

        auto_row = pygame.Rect(right.left + 12, right.top + 42 + len(RUN_SLOTS) * 52, right.width - 24, 40)
        auto_cols = split_columns(auto_row, [1, 1], gap=8)
        self.buttons.append(Button(auto_cols[0], "Equip Best", hotkey=pygame.K_b, on_click=lambda: self._equip_best(app), tooltip="Auto-equip best item for active slot (or all slots if none selected)."))
        self.buttons.append(Button(auto_cols[1], "Equip All", hotkey=pygame.K_a, on_click=lambda: self._equip_all(app), tooltip="Fill all slots using deterministic best-score planner."))

        bottom_cols = split_columns(pygame.Rect(rows[1].left + 8, rows[1].top + 8, rows[1].width - 16, rows[1].height - 16), [1, 1, 1, 1], gap=10)
        self.buttons.append(Button(bottom_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), tooltip="Return to base screen."))
        self.buttons.append(Button(bottom_cols[1], "Help", hotkey=pygame.K_h, on_click=lambda: self._show_help(), tooltip="Show quick loadout help."))
        self.buttons.append(Button(bottom_cols[2], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), tooltip="Open mission briefing and begin run."))
        self.buttons.append(Button(bottom_cols[3], "Clear All", on_click=lambda: self._clear_all(app), tooltip="Unequip all slots and return gear to storage."))

        self._left_rect = left
        self._right_rect = right
        self._bottom_rect = rows[1]

    def _clear_all(self, app) -> None:
        self._unequip_all(app)
        self._sync_citizen_loadout(app)
        app.save_current_slot()
        self._refresh_inventory(app)
        self.message = "Cleared all equipped items."

    def _show_help(self) -> None:
        self.help_overlay = True

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if self.help_overlay:
            if event.type in {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN}:
                self.help_overlay = False
            return
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
        mouse_pos = app.virtual_mouse_pos()

        for button in self.buttons:
            button.draw(surface, mouse_pos)
        if self.scroll_list:
            self.scroll_list.draw(surface)

        for run_slot, button in self._slot_buttons.items():
            current = getattr(app.current_loadout, run_slot)
            prefix = ">> " if self.active_slot == run_slot else ""
            button.text = f"{prefix}{run_slot}: {current or '-'}"
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
        for line in wrap_text(tags, theme.get_font(15), self._right_rect.width - 24):
            draw_text(surface, line, theme.get_font(15), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 14, y))
            y += 20
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
            item = app.content.item_by_id.get(self.selected_item_id)
            selected_name = item.name if item else self.selected_item_id
            draw_text(surface, f"Selected: {selected_name}", theme.get_font(16), theme.COLOR_ACCENT, (self._left_rect.left + 14, self._left_rect.bottom - 18), "midleft")
        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top - 34, self._bottom_rect.width - 16, 26)
            draw_tooltip_bar(surface, tip_rect, tip)
        if self.message:
            draw_text(surface, self.message, theme.get_font(17), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 8), "midbottom")
        if self.help_overlay:
            self._draw_help_overlay(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 210, 720, 420)
        Panel(rect, title="Loadout Help").draw(surface)
        lines = [
            "Choose gear from storage and assign it to slots.",
            "Equip Best uses deterministic scoring for the active slot.",
            "Equip All fills every slot with the best available plan.",
            "Tags from equipped items unlock event options in runs.",
            "Carry capacity and drain multipliers are shown on the right panel.",
            "Press any key to close.",
        ]
        y = rect.top + 52
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(17), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(17), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 22
            y += 3
