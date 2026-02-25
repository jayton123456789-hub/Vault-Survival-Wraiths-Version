from __future__ import annotations

import hashlib

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.claw_room import ClawRoom
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text, draw_tooltip_bar, hovered_tooltip, wrap_text
from bit_life_survival.core.crafting import can_craft, craft
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import citizen_queue_target, draft_citizen_from_claw, draft_selected_citizen, refill_citizen_queue, storage_used
from bit_life_survival.core.rng import DeterministicRNG
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


SLOT_FILTER_VALUES = ["all", "pack", "armor", "vehicle", "utility", "faction", "consumable"]
RARITY_FILTER_VALUES = ["all", "common", "uncommon", "rare", "legendary"]
MATERIAL_IDS = ("scrap", "cloth", "plastic", "metal")


class BaseScene(Scene):
    def __init__(self) -> None:
        self.message = ""
        self.selected_module = "storage"
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

        self.storage_scroll: ScrollList | None = None
        self._storage_rows: list[tuple[str, int]] = []
        self.selected_storage_item_id: str | None = None
        self.selected_slot_filter = "all"
        self.selected_rarity_filter = "all"

        self.crafting_scroll: ScrollList | None = None
        self._recipe_ids: list[str] = []
        self.selected_recipe_id: str | None = None

        self.help_overlay = False
        self.claw_room = ClawRoom()
        self._pending_claw_target_id: str | None = None
        self._claw_room_panel = pygame.Rect(0, 0, 0, 0)
        self._left_detail_rect = pygame.Rect(0, 0, 0, 0)
        self._right_top_rect = pygame.Rect(0, 0, 0, 0)
        self._right_bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._top_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._center_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)

    def _selected_citizen(self, app):
        selected_id = self.claw_room.selected_id
        if not selected_id:
            return None
        for citizen in app.save_data.vault.citizen_queue:
            if citizen.id == selected_id:
                return citizen
        return None

    def _predict_claw_target_id(self, app) -> str | None:
        queue = app.save_data.vault.citizen_queue
        if not queue:
            return None
        vault = app.save_data.vault
        rng = DeterministicRNG(
            seed=vault.settings.base_seed,
            state=vault.claw_rng_state,
            calls=vault.claw_rng_calls,
        )
        window = min(5, len(queue))
        idx = rng.next_int(0, max(1, window))
        return queue[idx].id

    def _start_claw_draft(self, app) -> None:
        if self.claw_room.is_animating:
            self.message = "Claw is already moving."
            return
        target_id = self._predict_claw_target_id(app)
        if target_id is None:
            self.message = "No citizens in queue."
            return
        if self.claw_room.start_grab(target_id):
            self._pending_claw_target_id = target_id
            target = next((c for c in app.save_data.vault.citizen_queue if c.id == target_id), None)
            label = target.name if target else "target"
            self.message = f"Claw locking onto {label}..."

    def _finalize_claw_draft(self, app, expected_id: str | None) -> None:
        drafted = draft_citizen_from_claw(app.save_data.vault, preview_count=5)
        app.current_loadout = drafted.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.claw_room.selected_id = drafted.id
        if expected_id and drafted.id != expected_id:
            self.message = f"Claw grabbed {drafted.name}."
        else:
            self.message = f"Drafted {drafted.name}."
        self._pending_claw_target_id = None

    def _draft_selected(self, app) -> None:
        if self.claw_room.is_animating:
            self.message = "Wait for claw animation to finish."
            return
        selected = self._selected_citizen(app)
        if selected is None:
            self.message = "Click a citizen in the claw room first."
            return
        drafted = draft_selected_citizen(app.save_data.vault, selected.id)
        app.current_loadout = drafted.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.claw_room.selected_id = drafted.id
        self.message = f"Drafted {drafted.name} from room."

    def _deploy(self, app) -> None:
        if app.save_data.vault.current_citizen is None:
            self.message = "Step 1: Draft a citizen with Use The Claw."
            return
        seed = app.compute_run_seed()
        app.save_data.vault.last_run_seed = seed
        app.save_data.vault.run_counter += 1
        app.save_current_slot()
        from .briefing import BriefingScene

        app.change_scene(BriefingScene(run_seed=seed))

    def _open_loadout(self, app) -> None:
        from .loadout import LoadoutScene

        app.change_scene(LoadoutScene())

    def _open_settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: BaseScene()))

    def _set_module(self, module: str) -> None:
        if module == self.selected_module:
            if module == "storage":
                self.message = "Storage is open. Select an item row to inspect details."
            elif module == "crafting":
                self.message = "Crafting is open. Select a recipe to preview requirements."
            else:
                self.message = "Drone Bay status is open."
            return
        self.selected_module = module
        if module == "storage":
            self.message = "Opened storage module."
        elif module == "crafting":
            self.message = "Opened crafting module."
        else:
            self.message = "Opened drone bay module."

    def _main_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _story_status(self, app) -> tuple[str, list[str], str]:
        vault = app.save_data.vault
        target = citizen_queue_target(vault)
        if vault.run_counter < 1:
            title = "Chapter 1: First Door"
            lines = [
                "You just sealed the vault hatch.",
                "Draft your first scavenger and gather parts.",
                "Every run powers the vault's next expansion.",
            ]
            objective = "Objective: complete your first deployment."
        elif vault.tav < 40:
            title = "Chapter 2: Power Grid"
            lines = [
                "The relay room still flickers.",
                "Bring back salvage to stabilize core systems.",
                "A stronger grid increases citizen capacity.",
            ]
            objective = f"Objective: reach Tech Value 40 (now {vault.tav})."
        elif vault.vault_level < 2:
            title = "Chapter 3: Expansion"
            lines = [
                "Support beams are ready for a new wing.",
                "Deploy often and keep citizens alive.",
                "Each milestone opens deeper expedition routes.",
            ]
            objective = "Objective: push vault level to 2."
        else:
            title = "Chapter 4: Long Haul"
            lines = [
                "The vault is operating, but the wasteland evolves.",
                "Rotate citizens, refine loadouts, and keep pressure up.",
                "Drone Bay upgrades reduce recovery losses.",
            ]
            objective = "Objective: maintain progress and rare recoveries."
        capacity_note = f"Citizen Capacity: {len(vault.citizen_queue)}/{target}"
        return title, lines, f"{objective}  {capacity_note}"

    def _cycle_storage_filter(self, app, which: str) -> None:
        if which == "slot":
            values = SLOT_FILTER_VALUES
            idx = values.index(self.selected_slot_filter)
            self.selected_slot_filter = values[(idx + 1) % len(values)]
        else:
            values = RARITY_FILTER_VALUES
            idx = values.index(self.selected_rarity_filter)
            self.selected_rarity_filter = values[(idx + 1) % len(values)]
        self._refresh_storage_rows(app)

    def _storage_matches_filters(self, item) -> bool:
        if self.selected_slot_filter != "all" and item.slot != self.selected_slot_filter:
            return False
        if self.selected_rarity_filter != "all" and item.rarity != self.selected_rarity_filter:
            return False
        return True

    def _refresh_storage_rows(self, app) -> None:
        rows: list[tuple[str, int]] = []
        for item_id, qty in sorted(app.save_data.vault.storage.items()):
            if qty <= 0:
                continue
            item = app.content.item_by_id.get(item_id)
            if not item or not self._storage_matches_filters(item):
                continue
            rows.append((item_id, qty))
        self._storage_rows = rows
        if self.storage_scroll:
            lines = [f"{app.content.item_by_id[item_id].name} x{qty}" for item_id, qty in rows]
            self.storage_scroll.set_items(lines)

    def _on_storage_select(self, index: int) -> None:
        if 0 <= index < len(self._storage_rows):
            self.selected_storage_item_id = self._storage_rows[index][0]

    def _refresh_recipe_rows(self, app) -> None:
        self._recipe_ids = [recipe.id for recipe in app.content.recipes]
        if self.crafting_scroll:
            self.crafting_scroll.set_items([app.content.recipe_by_id[rid].name for rid in self._recipe_ids])
        if self.selected_recipe_id not in app.content.recipe_by_id:
            self.selected_recipe_id = self._recipe_ids[0] if self._recipe_ids else None
        if self.crafting_scroll and self.selected_recipe_id in self._recipe_ids:
            self.crafting_scroll.selected_index = self._recipe_ids.index(self.selected_recipe_id)

    def _on_recipe_select(self, index: int) -> None:
        if 0 <= index < len(self._recipe_ids):
            self.selected_recipe_id = self._recipe_ids[index]

    def _craft_selected(self, app) -> None:
        if not self.selected_recipe_id:
            self.message = "Select a recipe first."
            return
        recipe = app.content.recipe_by_id.get(self.selected_recipe_id)
        if recipe is None:
            self.message = "Recipe missing."
            return
        if not craft(app.save_data.vault, recipe):
            self.message = f"Missing materials for {recipe.name}."
            return
        self.message = f"Crafted {recipe.output_qty}x {recipe.name}."
        app.save_current_slot()
        self._refresh_storage_rows(app)

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self.storage_scroll = None
        self.crafting_scroll = None

        root = app.screen.get_rect().inflate(-16, -16)
        top, body, bottom = split_rows(root, [0.16, 0.72, 0.12], gap=8)
        left, center, right = split_columns(body, [0.31, 0.39, 0.30], gap=8)
        self._top_rect, self._bottom_rect = top, bottom
        self._left_rect, self._center_rect, self._right_rect = left, center, right

        left_inner = pygame.Rect(left.left + 10, left.top + 36, left.width - 20, left.height - 46)
        room_panel, detail_panel, action_panel = split_rows(left_inner, [0.60, 0.24, 0.16], gap=8)
        self._claw_room_panel = room_panel
        self._left_detail_rect = detail_panel

        action_rows = split_rows(action_panel, [1, 1], gap=8)
        draft_btn = Button(action_rows[0], "Draft Selected", hotkey=pygame.K_RETURN, on_click=lambda: self._draft_selected(app), tooltip="Draft selected citizen.")
        claw_btn = Button(action_rows[1], "Use The Claw", hotkey=pygame.K_u, on_click=lambda: self._start_claw_draft(app), tooltip="Run claw machine draft.")
        draft_btn.bg = (70, 102, 90)
        draft_btn.bg_hover = (108, 146, 128)
        claw_btn.bg = (84, 112, 102)
        claw_btn.bg_hover = (122, 158, 140)
        self.buttons.extend([draft_btn, claw_btn])

        center_inner = pygame.Rect(center.left + 10, center.top + 36, center.width - 20, center.height - 46)
        tab_row = pygame.Rect(center_inner.left, center_inner.top, center_inner.width, 40)
        content_rect = pygame.Rect(center_inner.left, center_inner.top + 48, center_inner.width, center_inner.height - 48)
        tab_cols = split_columns(tab_row, [1, 1, 1], gap=8)
        self.buttons.extend(
            [
                Button(tab_cols[0], "Storage", on_click=lambda: self._set_module("storage"), tooltip="Open full storage module."),
                Button(tab_cols[1], "Crafting", on_click=lambda: self._set_module("crafting"), tooltip="Craft from materials."),
                Button(tab_cols[2], "Drone Bay", on_click=lambda: self._set_module("drone"), tooltip="Recovery system status."),
            ]
        )

        if self.selected_module == "storage":
            mat_row, filter_row, list_row = split_rows(content_rect, [0.18, 0.14, 0.68], gap=8)
            self._materials_rect = mat_row
            filter_cols = split_columns(filter_row, [1, 1], gap=8)
            self.buttons.append(Button(filter_cols[0], f"Slot: {self.selected_slot_filter}", on_click=lambda: self._cycle_storage_filter(app, "slot"), tooltip="Cycle slot filter."))
            self.buttons.append(Button(filter_cols[1], f"Rarity: {self.selected_rarity_filter}", on_click=lambda: self._cycle_storage_filter(app, "rarity"), tooltip="Cycle rarity filter."))
            self.storage_scroll = ScrollList(
                list_row,
                row_height=38,
                on_select=self._on_storage_select,
                row_renderer=lambda surf, rr, idx, text, selected, now: self._draw_storage_row(app, surf, rr, idx, text, selected),
            )
            self._refresh_storage_rows(app)
        elif self.selected_module == "crafting":
            list_row, button_row = split_rows(content_rect, [0.84, 0.16], gap=8)
            self.crafting_scroll = ScrollList(list_row, row_height=30, on_select=self._on_recipe_select)
            self._refresh_recipe_rows(app)
            recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
            craftable = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            craft_btn = Button(button_row, "Craft Selected", hotkey=pygame.K_RETURN, enabled=craftable, on_click=lambda: self._craft_selected(app), tooltip="Craft selected recipe.")
            craft_btn.bg = (82, 114, 102)
            craft_btn.bg_hover = (120, 156, 138)
            self.buttons.append(craft_btn)

        right_inner = pygame.Rect(right.left + 10, right.top + 36, right.width - 20, right.height - 46)
        self._right_top_rect, self._right_bottom_rect = split_rows(right_inner, [0.46, 0.54], gap=8)

        bottom_cols = split_columns(
            pygame.Rect(bottom.left + 8, bottom.top + 8, bottom.width - 16, bottom.height - 16),
            [1, 1, 1, 1, 1],
            gap=8,
        )
        loadout_btn = Button(bottom_cols[0], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app), tooltip="Open loadout.")
        storage_btn = Button(bottom_cols[1], "Storage", hotkey=pygame.K_g, on_click=lambda: self._set_module("storage"), tooltip="Focus storage module.")
        deploy_btn = Button(bottom_cols[2], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), tooltip="Start briefing and run.")
        settings_btn = Button(bottom_cols[3], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Open settings.")
        menu_btn = Button(bottom_cols[4], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._main_menu(app), tooltip="Return to menu.")
        loadout_btn.bg = (86, 112, 98)
        storage_btn.bg = (78, 116, 120)
        deploy_btn.bg = (76, 124, 92)
        settings_btn.bg = (86, 106, 112)
        menu_btn.bg = (116, 72, 82)
        loadout_btn.bg_hover = (120, 152, 132)
        storage_btn.bg_hover = (108, 152, 164)
        deploy_btn.bg_hover = (106, 162, 122)
        settings_btn.bg_hover = (118, 142, 152)
        menu_btn.bg_hover = (154, 96, 110)
        self.buttons.extend([loadout_btn, storage_btn, deploy_btn, settings_btn, menu_btn])

    def _draw_storage_row(
        self,
        app,
        surface: pygame.Surface,
        row_rect: pygame.Rect,
        index: int,
        _text: str,
        selected: bool,
    ) -> None:
        if index < 0 or index >= len(self._storage_rows):
            return
        item_id, qty = self._storage_rows[index]
        item = app.content.item_by_id.get(item_id)
        icon_rect = pygame.Rect(row_rect.left + 5, row_rect.top + 5, row_rect.height - 10, row_rect.height - 10)
        self._draw_item_icon(surface, icon_rect, item_id)
        name = item.name if item else item_id
        label_color = theme.COLOR_TEXT if not selected else (242, 245, 232)
        draw_text(surface, f"{name}", theme.get_font(15, bold=True), label_color, (icon_rect.right + 8, row_rect.top + 5))
        meta = f"{item.rarity if item else 'common'} | {item.slot if item else 'item'}"
        draw_text(surface, meta, theme.get_font(12), theme.COLOR_TEXT_MUTED, (icon_rect.right + 8, row_rect.top + 20))
        draw_text(surface, f"x{qty}", theme.get_font(14, bold=True), theme.COLOR_TEXT, (row_rect.right - 8, row_rect.centery), "midright")

    def _draw_item_icon(self, surface: pygame.Surface, rect: pygame.Rect, item_id: str) -> None:
        digest = hashlib.sha256(item_id.encode("utf-8")).digest()
        outer = (52 + digest[0] % 80, 44 + digest[1] % 70, 64 + digest[2] % 70)
        inner = (96 + digest[3] % 100, 92 + digest[4] % 100, 106 + digest[5] % 90)
        pygame.draw.rect(surface, outer, rect, border_radius=2)
        inset = rect.inflate(-4, -4)
        pygame.draw.rect(surface, inner, inset, border_radius=2)
        shape = digest[6] % 3
        if shape == 0:
            pygame.draw.circle(surface, (220, 210, 178), inset.center, max(2, inset.width // 3))
        elif shape == 1:
            pygame.draw.rect(surface, (220, 210, 178), pygame.Rect(inset.left + 2, inset.top + 2, inset.width - 4, inset.height - 4), width=2)
        else:
            pygame.draw.line(surface, (220, 210, 178), (inset.left + 2, inset.bottom - 2), (inset.right - 2, inset.top + 2), 2)

    def _draw_top_bar(self, app, surface: pygame.Surface) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        line1 = (
            f"Vault Lv {vault.vault_level}    "
            f"Tech Value (TAV) {vault.tav}    "
            f"Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}    "
            f"Storage Used {used}"
        )
        draw_text(surface, line1, theme.get_font(22, bold=True), theme.COLOR_TEXT, (self._top_rect.left + 14, self._top_rect.top + 52))

    def _draw_materials_row(self, app, surface: pygame.Surface) -> None:
        draw_text(surface, "Materials Pouch", theme.get_font(15, bold=True), theme.COLOR_TEXT_MUTED, (self._materials_rect.left + 6, self._materials_rect.top + 4))
        row = pygame.Rect(self._materials_rect.left, self._materials_rect.top + 22, self._materials_rect.width, self._materials_rect.height - 24)
        cols = split_columns(row, [1, 1, 1, 1], gap=8)
        for col, mid in zip(cols, MATERIAL_IDS):
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=2, border_radius=2)
            draw_text(surface, f"{mid.title()} {app.save_data.vault.materials.get(mid, 0)}", theme.get_font(15, bold=True), theme.COLOR_TEXT, col.center, "center")

    def _draw_left_detail(self, app, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._left_detail_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._left_detail_rect, width=2, border_radius=2)
        y = self._left_detail_rect.top + 8
        selected = self._selected_citizen(app)
        draw_text(surface, "Citizen Detail", theme.get_font(15, bold=True), theme.COLOR_TEXT, (self._left_detail_rect.left + 8, y))
        y += 18
        if selected:
            draw_text(surface, selected.name, theme.get_font(15, bold=True), theme.COLOR_SUCCESS, (self._left_detail_rect.left + 8, y))
            y += 16
            for line in wrap_text(selected.quirk, theme.get_font(12), self._left_detail_rect.width - 16)[:2]:
                draw_text(surface, line, theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._left_detail_rect.left + 8, y))
                y += 14
        else:
            draw_text(surface, "Click a citizen in the room.", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._left_detail_rect.left + 8, y))
            y += 14
        current = app.save_data.vault.current_citizen
        label = current.name if current else "None"
        draw_text(surface, f"Current Draft: {label}", theme.get_font(12, bold=True), theme.COLOR_TEXT, (self._left_detail_rect.left + 8, self._left_detail_rect.bottom - 14))

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        # Onboarding card
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._right_top_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._right_top_rect, width=2, border_radius=2)
        y = self._right_top_rect.top + 8
        chapter, lore_lines, objective_line = self._story_status(app)
        draw_text(surface, chapter, theme.get_font(16, bold=True), theme.COLOR_TEXT, (self._right_top_rect.left + 8, y))
        y += 20
        for line in lore_lines:
            for wrapped in wrap_text(line, theme.get_font(12), self._right_top_rect.width - 16):
                draw_text(surface, wrapped, theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_top_rect.left + 8, y))
                y += 14
            y += 1
        y += 2
        draw_text(surface, "What To Do Next", theme.get_font(16, bold=True), theme.COLOR_TEXT, (self._right_top_rect.left + 8, y))
        y += 20
        has_citizen = app.save_data.vault.current_citizen is not None
        has_loadout = any(bool(v) for v in app.current_loadout.model_dump(mode="python").values())
        steps = [
            ("Draft a citizen", has_citizen),
            ("Open Loadout and equip gear", has_loadout),
            ("Press Deploy to start run", has_citizen),
        ]
        for text, done in steps:
            prefix = "[OK]" if done else "[  ]"
            color = theme.COLOR_SUCCESS if done else theme.COLOR_TEXT
            draw_text(surface, f"{prefix} {text}", theme.get_font(14, bold=done), color, (self._right_top_rect.left + 8, y))
            y += 18
        if not has_citizen:
            draw_text(surface, "Tip: Use The Claw to draft.", theme.get_font(13), theme.COLOR_WARNING, (self._right_top_rect.left + 8, self._right_top_rect.bottom - 30))
        draw_text(surface, objective_line, theme.get_font(11), theme.COLOR_TEXT_MUTED, (self._right_top_rect.left + 8, self._right_top_rect.bottom - 14))

        # Lower detail panel
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._right_bottom_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._right_bottom_rect, width=2, border_radius=2)

        if self.selected_module == "storage" and self.selected_storage_item_id:
            item = app.content.item_by_id.get(self.selected_storage_item_id)
            if item:
                y = self._right_bottom_rect.top + 8
                draw_text(surface, item.name, theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
                y += 20
                draw_text(surface, f"{item.rarity} | {item.slot}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_bottom_rect.left + 8, y))
                y += 14
                tags = ", ".join(item.tags) if item.tags else "-"
                for line in wrap_text(f"Tags: {tags}", theme.get_font(12), self._right_bottom_rect.width - 16):
                    draw_text(surface, line, theme.get_font(12), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
                    y += 14
                y += 4
                mods = item.modifiers.model_dump(mode="python", exclude_none=True)
                for key, value in mods.items():
                    draw_text(surface, f"{key}: {value:+.2f}" if isinstance(value, float) else f"{key}: {value}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_bottom_rect.left + 8, y))
                    y += 14
                return

        if self.selected_module == "crafting" and self.selected_recipe_id:
            recipe = app.content.recipe_by_id.get(self.selected_recipe_id)
            if recipe:
                craftable, requirements = can_craft(app.save_data.vault, recipe)
                y = self._right_bottom_rect.top + 8
                draw_text(surface, recipe.name, theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
                y += 20
                for material_id, (have, need) in requirements.items():
                    color = theme.COLOR_SUCCESS if have >= need else theme.COLOR_WARNING
                    draw_text(surface, f"{material_id.title()}: {have}/{need}", theme.get_font(12, bold=True), color, (self._right_bottom_rect.left + 8, y))
                    y += 14
                y += 4
                draw_text(surface, "Craftable" if craftable else "Missing materials", theme.get_font(12, bold=True), theme.COLOR_SUCCESS if craftable else theme.COLOR_WARNING, (self._right_bottom_rect.left + 8, y))
                return

        preview_state = GameState(seed=0, biome_id="suburbs", rng_state=1, rng_calls=0, equipped=app.current_loadout.model_copy(deep=True))
        summary = compute_loadout_summary(preview_state, app.content)
        y = self._right_bottom_rect.top + 8
        draw_text(surface, "Loadout Preview", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
        y += 20
        for slot_name, item_id in app.current_loadout.model_dump(mode="python").items():
            draw_text(surface, f"{slot_name}: {item_id or '-'}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_bottom_rect.left + 8, y))
            y += 14
        y += 4
        draw_text(surface, f"Tags: {', '.join(summary['tags']) if summary['tags'] else '-'}", theme.get_font(12), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
        y += 14
        draw_text(surface, f"Speed {summary['speed_bonus']:+.2f}  Carry {summary['carry_bonus']:+.1f}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_bottom_rect.left + 8, y))

    def update(self, app, dt: float) -> None:
        if app.save_data is None:
            return
        refill_citizen_queue(app.save_data.vault)
        self.claw_room.sync(app.save_data.vault.citizen_queue)
        self.claw_room.update(dt)
        finished_target = self.claw_room.consume_finished_target()
        if finished_target is not None:
            self._finalize_claw_draft(app, expected_id=finished_target)

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if self.help_overlay:
            if event.type in {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN}:
                self.help_overlay = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.help_overlay = True
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._claw_room_panel.collidepoint(event.pos):
            self.claw_room.pick_actor(event.pos)
            return

        if self.storage_scroll and self.storage_scroll.handle_event(event):
            return
        if self.crafting_scroll and self.crafting_scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def render(self, app, surface: pygame.Surface) -> None:
        if app.save_data is None:
            from .menu import MainMenuScene

            app.change_scene(MainMenuScene("No save loaded."))
            return

        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._left_rect, title="Citizen Line").draw(surface)
        Panel(self._center_rect, title="Vault Modules").draw(surface)
        Panel(self._right_rect, title="Mission Context").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface)
        self.claw_room.draw(surface, self._claw_room_panel, app.save_data.vault.citizen_queue)
        self._draw_left_detail(app, surface)

        if self.selected_module == "storage":
            self._draw_materials_row(app, surface)
            if self.storage_scroll:
                draw_text(
                    surface,
                    "Gear Storage",
                    theme.get_font(14, bold=True),
                    theme.COLOR_TEXT_MUTED,
                    (self.storage_scroll.rect.left + 2, self.storage_scroll.rect.top - 16),
                )
            if self.storage_scroll:
                self.storage_scroll.draw(surface)
        elif self.selected_module == "crafting":
            if self.crafting_scroll:
                self.crafting_scroll.draw(surface)
        else:
            center_inner = pygame.Rect(self._center_rect.left + 20, self._center_rect.top + 92, self._center_rect.width - 40, self._center_rect.height - 108)
            draw_text(surface, "Drone Bay Status", theme.get_font(18, bold=True), theme.COLOR_TEXT, (center_inner.left, center_inner.top))
            lines = [
                f"Level: {int(app.save_data.vault.upgrades.get('drone_bay_level', 0))}",
                "Higher levels improve return quality.",
                "Retreating applies a recovery penalty.",
            ]
            y = center_inner.top + 28
            for line in lines:
                draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT_MUTED, (center_inner.left, y))
                y += 20

        self._draw_right_panel(app, surface)

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            if button.text in {"Storage", "Crafting", "Drone Bay"}:
                active = (
                    (button.text == "Storage" and self.selected_module == "storage")
                    or (button.text == "Crafting" and self.selected_module == "crafting")
                    or (button.text == "Drone Bay" and self.selected_module == "drone")
                )
                if active:
                    button.bg = (106, 132, 118)
                    button.bg_hover = (134, 164, 146)
                else:
                    button.bg = (82, 110, 98)
                    button.bg_hover = (114, 146, 130)
            if button.text == "Craft Selected":
                recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
                button.enabled = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            button.draw(surface, mouse_pos)

        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top - 22, self._bottom_rect.width - 16, 18)
            draw_tooltip_bar(surface, tip_rect, tip)

        if self.message:
            draw_text(surface, self.message, theme.get_font(15), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 5), "midbottom")
        if self.help_overlay:
            self._draw_help_overlay(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 220, 720, 440)
        Panel(rect, title="Base Help").draw(surface)
        lines = [
            "Citizens move in the claw room. Click one to inspect.",
            "Use The Claw runs a deterministic claw-machine draft.",
            "Draft Selected drafts the currently highlighted citizen.",
            "Materials pouch is separate from gear storage capacity.",
            "Loadout -> Deploy -> Run is the main loop.",
            "Press any key to close.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(17), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(17), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 22
            y += 3
