from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.avatar import draw_citizen_avatar
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text, draw_tooltip_bar, hovered_tooltip, wrap_text
from bit_life_survival.core.crafting import can_craft, craft
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import draft_citizen_from_claw, draft_selected_citizen, refill_citizen_queue, storage_used
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

        self.citizen_scroll: ScrollList | None = None
        self._citizen_rows: list[str] = []
        self.selected_citizen_index: int | None = None

        self.crafting_scroll: ScrollList | None = None
        self._recipe_ids: list[str] = []
        self.selected_recipe_id: str | None = None
        self.help_overlay = False

        self._top_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._center_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._citizen_detail_rect = pygame.Rect(0, 0, 0, 0)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)

    def _deploy(self, app) -> None:
        if app.save_data.vault.current_citizen is None:
            self.message = "Step 1: Draft a citizen with Use The Claw."
            return
        if app.current_slot is None:
            self.message = "No save slot loaded."
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

    def _main_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _claw(self, app) -> None:
        drafted = draft_citizen_from_claw(app.save_data.vault, preview_count=5)
        app.current_loadout = drafted.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.message = f"Drafted {drafted.name}. Next: open Loadout or press Deploy."

    def _draft_selected(self, app) -> None:
        if self.selected_citizen_index is None:
            self.message = "Select a citizen from the line first."
            return
        queue = app.save_data.vault.citizen_queue
        if self.selected_citizen_index < 0 or self.selected_citizen_index >= len(queue):
            self.message = "Selected citizen is no longer available."
            return
        drafted = draft_selected_citizen(app.save_data.vault, queue[self.selected_citizen_index].id)
        app.current_loadout = drafted.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.message = f"Drafted {drafted.name} from queue."
        self._refresh_citizen_rows(app)

    def _refresh_citizen_rows(self, app) -> None:
        queue = app.save_data.vault.citizen_queue
        self._citizen_rows = [citizen.name for citizen in queue]
        if self.citizen_scroll:
            self.citizen_scroll.set_items(self._citizen_rows)
        if self.selected_citizen_index is not None and self.selected_citizen_index >= len(queue):
            self.selected_citizen_index = None

    def _on_select_citizen(self, index: int) -> None:
        if 0 <= index < len(self._citizen_rows):
            self.selected_citizen_index = index

    def _selected_citizen(self, app):
        if self.selected_citizen_index is not None:
            if 0 <= self.selected_citizen_index < len(app.save_data.vault.citizen_queue):
                return app.save_data.vault.citizen_queue[self.selected_citizen_index]
        return None

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
            self.storage_scroll.set_items([f"{app.content.item_by_id[item_id].name} x{qty}" for item_id, qty in rows])

    def _on_storage_select(self, index: int) -> None:
        if 0 <= index < len(self._storage_rows):
            self.selected_storage_item_id = self._storage_rows[index][0]

    def _craft_recipe(self, app, recipe_id: str) -> None:
        recipe = app.content.recipe_by_id.get(recipe_id)
        if recipe is None:
            self.message = f"Recipe '{recipe_id}' missing."
            return
        if not craft(app.save_data.vault, recipe):
            self.message = f"Missing materials for {recipe.name}."
            return
        app.save_current_slot()
        self._refresh_storage_rows(app)
        self.message = f"Crafted {recipe.output_qty}x {recipe.name}."

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
        self._craft_recipe(app, self.selected_recipe_id)

    def _draw_citizen_row(self, app, surface: pygame.Surface, row_rect: pygame.Rect, index: int, _text: str, selected: bool, now_s: float) -> None:
        if index < 0 or index >= len(app.save_data.vault.citizen_queue):
            return
        citizen = app.save_data.vault.citizen_queue[index]
        avatar_rect = pygame.Rect(row_rect.left + 4, row_rect.top + 2, row_rect.height - 4, row_rect.height - 4)
        draw_citizen_avatar(surface, avatar_rect, citizen.id, citizen.name, selected=selected, time_s=now_s)
        draw_text(surface, f"{index + 1:02d}. {citizen.name}", theme.get_font(15, bold=True), theme.COLOR_TEXT, (avatar_rect.right + 8, row_rect.top + 6))
        quirk = citizen.quirk if len(citizen.quirk) <= 28 else citizen.quirk[:25] + "..."
        draw_text(surface, quirk, theme.get_font(12), theme.COLOR_TEXT_MUTED, (avatar_rect.right + 8, row_rect.top + 22))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []

        root = app.screen.get_rect().inflate(-16, -16)
        rows = split_rows(root, [0.15, 0.73, 0.12], gap=8)
        body_cols = split_columns(rows[1], [0.30, 0.40, 0.30], gap=8)
        self._top_rect, self._bottom_rect = rows[0], rows[2]
        self._left_rect, self._center_rect, self._right_rect = body_cols

        left_inner = pygame.Rect(self._left_rect.left + 10, self._left_rect.top + 36, self._left_rect.width - 20, self._left_rect.height - 46)
        left_rows = split_rows(left_inner, [0.60, 0.24, 0.16], gap=8)
        list_zone, self._citizen_detail_rect, action_zone = left_rows

        list_label_rect = pygame.Rect(list_zone.left, list_zone.top, list_zone.width, 20)
        self._citizen_header_rect = list_label_rect
        citizen_scroll_rect = pygame.Rect(list_zone.left, list_zone.top + 22, list_zone.width, list_zone.height - 22)
        self.citizen_scroll = ScrollList(
            citizen_scroll_rect,
            row_height=38,
            on_select=self._on_select_citizen,
            row_renderer=lambda surface, row_rect, idx, text, sel, now: self._draw_citizen_row(app, surface, row_rect, idx, text, sel, now),
        )
        self._refresh_citizen_rows(app)

        action_rows = split_rows(action_zone, [1, 1], gap=8)
        draft_button = Button(action_rows[0], "Draft Selected", hotkey=pygame.K_RETURN, on_click=lambda: self._draft_selected(app), tooltip="Draft highlighted citizen.")
        claw_button = Button(action_rows[1], "Use The Claw", hotkey=pygame.K_u, on_click=lambda: self._claw(app), tooltip="Random draft from front of queue.")
        draft_button.bg = (70, 102, 90)
        claw_button.bg = (84, 112, 102)
        draft_button.bg_hover = (110, 150, 130)
        claw_button.bg_hover = (120, 154, 138)
        self.buttons.extend([draft_button, claw_button])

        center_inner = pygame.Rect(self._center_rect.left + 10, self._center_rect.top + 36, self._center_rect.width - 20, self._center_rect.height - 46)
        module_tabs_row = pygame.Rect(center_inner.left, center_inner.top, center_inner.width, 42)
        module_content = pygame.Rect(center_inner.left, center_inner.top + 50, center_inner.width, center_inner.height - 50)
        module_cols = split_columns(module_tabs_row, [1, 1, 1], gap=8)
        storage_btn = Button(module_cols[0], "Storage", on_click=lambda: setattr(self, "selected_module", "storage"), tooltip="Manage gear inventory.")
        crafting_btn = Button(module_cols[1], "Crafting", on_click=lambda: setattr(self, "selected_module", "crafting"), tooltip="Craft from materials.")
        drone_btn = Button(module_cols[2], "Drone Bay", on_click=lambda: setattr(self, "selected_module", "drone"), tooltip="Recovery readiness.")
        for b in (storage_btn, crafting_btn, drone_btn):
            b.bg = (80, 108, 95)
            b.bg_hover = (112, 146, 132)
        self.buttons.extend([storage_btn, crafting_btn, drone_btn])

        self.storage_scroll = None
        self.crafting_scroll = None
        self._materials_rect = pygame.Rect(0, 0, 0, 0)
        self._module_hint_rect = pygame.Rect(0, 0, 0, 0)

        if self.selected_module == "storage":
            module_rows = split_rows(module_content, [0.15, 0.12, 0.73], gap=8)
            self._materials_rect, filter_rect, list_rect = module_rows
            filter_cols = split_columns(filter_rect, [1, 1], gap=8)
            self.buttons.append(
                Button(
                    filter_cols[0],
                    f"Slot: {self.selected_slot_filter}",
                    on_click=lambda: self._cycle_storage_filter(app, "slot"),
                    tooltip="Cycle slot filter.",
                )
            )
            self.buttons.append(
                Button(
                    filter_cols[1],
                    f"Rarity: {self.selected_rarity_filter}",
                    on_click=lambda: self._cycle_storage_filter(app, "rarity"),
                    tooltip="Cycle rarity filter.",
                )
            )
            self.storage_scroll = ScrollList(list_rect, row_height=30, on_select=self._on_storage_select)
            self._refresh_storage_rows(app)
            self._module_hint_rect = pygame.Rect(filter_rect.left, filter_rect.bottom + 2, filter_rect.width, 14)
        elif self.selected_module == "crafting":
            module_rows = split_rows(module_content, [0.82, 0.18], gap=8)
            self.crafting_scroll = ScrollList(module_rows[0], row_height=30, on_select=self._on_recipe_select)
            self._refresh_recipe_rows(app)
            recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
            craftable = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            craft_btn = Button(module_rows[1], "Craft Selected", hotkey=pygame.K_RETURN, enabled=craftable, on_click=lambda: self._craft_selected(app), tooltip="Craft selected recipe.")
            craft_btn.bg = (82, 114, 102)
            craft_btn.bg_hover = (118, 156, 138)
            self.buttons.append(craft_btn)
        else:
            self._module_hint_rect = module_content

        bottom_cols = split_columns(
            pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top + 8, self._bottom_rect.width - 16, self._bottom_rect.height - 16),
            [1, 1, 1, 1],
            gap=8,
        )
        loadout_btn = Button(bottom_cols[0], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app), tooltip="Configure equipment.")
        deploy_btn = Button(bottom_cols[1], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), tooltip="Begin briefing and run.")
        settings_btn = Button(bottom_cols[2], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Open settings.")
        menu_btn = Button(bottom_cols[3], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._main_menu(app), tooltip="Return to front menu.")
        loadout_btn.bg = (86, 112, 98)
        deploy_btn.bg = (78, 124, 92)
        settings_btn.bg = (86, 106, 112)
        menu_btn.bg = (116, 72, 82)
        loadout_btn.bg_hover = (114, 152, 132)
        deploy_btn.bg_hover = (108, 164, 122)
        settings_btn.bg_hover = (116, 142, 152)
        menu_btn.bg_hover = (150, 94, 106)
        self.buttons.extend([loadout_btn, deploy_btn, settings_btn, menu_btn])

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
        if self.storage_scroll and self.storage_scroll.handle_event(event):
            return
        if self.citizen_scroll and self.citizen_scroll.handle_event(event):
            return
        if self.crafting_scroll and self.crafting_scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_top_bar(self, app, surface: pygame.Surface) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        left_line = f"Vault Lv {vault.vault_level}    TAV {vault.tav}    Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}    Storage Used {used}"
        mats = vault.materials
        right_line = f"Scrap {mats.get('scrap', 0)}   Cloth {mats.get('cloth', 0)}   Plastic {mats.get('plastic', 0)}   Metal {mats.get('metal', 0)}"
        draw_text(surface, left_line, theme.get_font(20, bold=True), theme.COLOR_TEXT, (self._top_rect.left + 14, self._top_rect.top + 42))
        draw_text(surface, right_line, theme.get_font(19, bold=True), theme.COLOR_TEXT_MUTED, (self._top_rect.left + 14, self._top_rect.top + 68))

    def _draw_materials_pouch(self, app, surface: pygame.Surface) -> None:
        draw_text(surface, "Materials Pouch", theme.get_font(14, bold=True), theme.COLOR_TEXT_MUTED, (self._materials_rect.left + 6, self._materials_rect.top + 4))
        row = pygame.Rect(self._materials_rect.left, self._materials_rect.top + 20, self._materials_rect.width, self._materials_rect.height - 20)
        cols = split_columns(row, [1, 1, 1, 1], gap=8)
        for col, mid in zip(cols, MATERIAL_IDS):
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=2, border_radius=2)
            draw_text(surface, f"{mid.title()} {app.save_data.vault.materials.get(mid, 0)}", theme.get_font(15, bold=True), theme.COLOR_TEXT, col.center, "center")

    def _draw_storage_module(self, app, surface: pygame.Surface) -> None:
        if self.selected_module == "storage":
            self._draw_materials_pouch(app, surface)
            if self.storage_scroll:
                self.storage_scroll.draw(surface)
            draw_text(surface, "Materials are separate from gear capacity.", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._module_hint_rect.left, self._module_hint_rect.top))
            return

        if self.selected_module == "crafting":
            if self.crafting_scroll:
                self.crafting_scroll.draw(surface)
            return

        level = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
        lines = [
            f"Drone Bay Level: {level}",
            "Recovery quality scales with drone upgrades.",
            "Retreating applies a recovery penalty.",
        ]
        y = self._module_hint_rect.top + 8
        for line in lines:
            draw_text(surface, line, theme.get_font(17), theme.COLOR_TEXT, (self._module_hint_rect.left + 8, y))
            y += 24

    def _draw_onboarding(self, app, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, rect, width=2, border_radius=2)
        draw_text(surface, "What To Do Next", theme.get_font(17, bold=True), theme.COLOR_TEXT, (rect.left + 8, rect.top + 6))

        has_citizen = app.save_data.vault.current_citizen is not None
        has_loadout = any(bool(v) for v in app.current_loadout.model_dump(mode="python").values())
        steps = [
            ("1. Draft a citizen", has_citizen),
            ("2. Open Loadout and equip gear", has_loadout),
            ("3. Press Deploy to start the run", has_citizen),
        ]
        y = rect.top + 34
        for label, done in steps:
            prefix = "[OK]" if done else "[  ]"
            color = theme.COLOR_SUCCESS if done else theme.COLOR_TEXT
            draw_text(surface, f"{prefix} {label}", theme.get_font(14, bold=done), color, (rect.left + 8, y))
            y += 18

        if not has_citizen:
            draw_text(surface, "Tip: Start with Use The Claw.", theme.get_font(13), theme.COLOR_WARNING, (rect.left + 8, rect.bottom - 18))

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        right_inner = pygame.Rect(self._right_rect.left + 10, self._right_rect.top + 36, self._right_rect.width - 20, self._right_rect.height - 46)
        right_rows = split_rows(right_inner, [0.28, 0.28, 0.44], gap=8)
        guide_rect, citizen_rect, detail_rect = right_rows
        self._draw_onboarding(app, surface, guide_rect)

        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, citizen_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, citizen_rect, width=2, border_radius=2)
        draw_text(surface, "Drafted Citizen", theme.get_font(17, bold=True), theme.COLOR_TEXT, (citizen_rect.left + 8, citizen_rect.top + 6))
        current = app.save_data.vault.current_citizen
        if current:
            avatar_rect = pygame.Rect(citizen_rect.left + 8, citizen_rect.top + 28, 56, 56)
            draw_citizen_avatar(surface, avatar_rect, current.id, current.name, selected=True, time_s=pygame.time.get_ticks() / 1000.0)
            draw_text(surface, current.name, theme.get_font(17, bold=True), theme.COLOR_SUCCESS, (avatar_rect.right + 10, citizen_rect.top + 34))
            draw_text(surface, current.quirk, theme.get_font(13), theme.COLOR_TEXT_MUTED, (avatar_rect.right + 10, citizen_rect.top + 54))
        else:
            draw_text(surface, "No drafted citizen yet.", theme.get_font(14), theme.COLOR_TEXT_MUTED, (citizen_rect.left + 8, citizen_rect.top + 34))

        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, detail_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, detail_rect, width=2, border_radius=2)

        if self.selected_module == "crafting" and self.selected_recipe_id:
            recipe = app.content.recipe_by_id.get(self.selected_recipe_id)
            if recipe:
                craftable, requirements = can_craft(app.save_data.vault, recipe)
                y = detail_rect.top + 8
                draw_text(surface, recipe.name, theme.get_font(16, bold=True), theme.COLOR_TEXT, (detail_rect.left + 8, y))
                y += 20
                if recipe.description:
                    for line in wrap_text(recipe.description, theme.get_font(12), detail_rect.width - 16)[:2]:
                        draw_text(surface, line, theme.get_font(12), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))
                        y += 14
                y += 4
                for material_id, (have, need) in requirements.items():
                    color = theme.COLOR_SUCCESS if have >= need else theme.COLOR_WARNING
                    draw_text(surface, f"{material_id.title()}: {have}/{need}", theme.get_font(12, bold=True), color, (detail_rect.left + 8, y))
                    y += 14
                y += 4
                out_item = app.content.item_by_id.get(recipe.output_item)
                out_name = out_item.name if out_item else recipe.output_item
                draw_text(surface, f"Output: {out_name} x{recipe.output_qty}", theme.get_font(12), theme.COLOR_TEXT, (detail_rect.left + 8, y))
                y += 14
                draw_text(surface, "Craftable" if craftable else "Missing materials", theme.get_font(12, bold=True), theme.COLOR_SUCCESS if craftable else theme.COLOR_WARNING, (detail_rect.left + 8, y))
                return

        if self.selected_module == "storage" and self.selected_storage_item_id:
            item = app.content.item_by_id.get(self.selected_storage_item_id)
            if item:
                y = detail_rect.top + 8
                draw_text(surface, item.name, theme.get_font(16, bold=True), theme.COLOR_TEXT, (detail_rect.left + 8, y))
                y += 20
                draw_text(surface, f"Slot {item.slot} | {item.rarity}", theme.get_font(13), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))
                y += 18
                tags = ", ".join(item.tags) if item.tags else "-"
                for line in wrap_text(f"Tags: {tags}", theme.get_font(13), detail_rect.width - 16):
                    draw_text(surface, line, theme.get_font(13), theme.COLOR_TEXT, (detail_rect.left + 8, y))
                    y += 16
                y += 4
                mods = item.modifiers.model_dump(mode="python", exclude_none=True)
                for key, value in mods.items():
                    draw_text(surface, f"{key}: {value:+.2f}" if isinstance(value, float) else f"{key}: {value}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))
                    y += 14
                return

        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        y = detail_rect.top + 8
        draw_text(surface, "Loadout Preview", theme.get_font(16, bold=True), theme.COLOR_TEXT, (detail_rect.left + 8, y))
        y += 20
        for slot_name, item_id in app.current_loadout.model_dump(mode="python").items():
            draw_text(surface, f"{slot_name}: {item_id or '-'}", theme.get_font(13), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))
            y += 14
        y += 2
        draw_text(surface, f"Tags: {', '.join(summary['tags']) if summary['tags'] else '-'}", theme.get_font(12), theme.COLOR_TEXT, (detail_rect.left + 8, y))
        y += 16
        draw_text(surface, f"Speed {summary['speed_bonus']:+.2f}  Carry {summary['carry_bonus']:+.1f}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))
        y += 14
        draw_text(surface, f"Injury Resist {summary['injury_resist']*100:.0f}%  Noise {summary['noise']:+.2f}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (detail_rect.left + 8, y))

    def _draw_citizen_details(self, app, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._citizen_detail_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._citizen_detail_rect, width=2, border_radius=2)
        y = self._citizen_detail_rect.top + 6
        draw_text(surface, "Citizen Details", theme.get_font(15, bold=True), theme.COLOR_TEXT, (self._citizen_detail_rect.left + 8, y))
        y += 18
        selected = self._selected_citizen(app)
        if selected:
            draw_text(surface, selected.name, theme.get_font(14, bold=True), theme.COLOR_SUCCESS, (self._citizen_detail_rect.left + 8, y))
            y += 16
            draw_text(surface, selected.quirk, theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._citizen_detail_rect.left + 8, y))
            y += 14
            kit = ", ".join(f"{item} x{qty}" for item, qty in sorted(selected.kit.items())) or "None"
            for line in wrap_text(f"Kit: {kit}", theme.get_font(12), self._citizen_detail_rect.width - 16)[:2]:
                draw_text(surface, line, theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._citizen_detail_rect.left + 8, y))
                y += 14
        else:
            draw_text(surface, "Select a citizen row to inspect.", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._citizen_detail_rect.left + 8, y))
            y += 14
        current = app.save_data.vault.current_citizen
        label = current.name if current else "None"
        draw_text(surface, f"Current Draft: {label}", theme.get_font(12, bold=True), theme.COLOR_TEXT, (self._citizen_detail_rect.left + 8, self._citizen_detail_rect.bottom - 16))

    def render(self, app, surface: pygame.Surface) -> None:
        if app.save_data is None:
            from .menu import MainMenuScene

            app.change_scene(MainMenuScene("No save loaded."))
            return
        refill_citizen_queue(app.save_data.vault, target_size=12)
        self._build_layout(app)

        app.backgrounds.draw(surface, "vault")
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._left_rect, title="Citizen Line").draw(surface)
        Panel(self._center_rect, title="Vault Modules").draw(surface)
        Panel(self._right_rect, title="Mission Context").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface)
        draw_text(surface, f"Queued Citizens: {len(app.save_data.vault.citizen_queue)}", theme.get_font(15, bold=True), theme.COLOR_TEXT, (self._citizen_header_rect.left + 2, self._citizen_header_rect.top + 2))

        if self.citizen_scroll:
            self.citizen_scroll.draw(surface)
        self._draw_citizen_details(app, surface)
        self._draw_storage_module(app, surface)
        self._draw_right_panel(app, surface)

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            if button.text == "Craft Selected":
                recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
                button.enabled = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            button.draw(surface, mouse_pos)

        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top - 26, self._bottom_rect.width - 16, 20)
            draw_tooltip_bar(surface, tip_rect, tip)

        if self.message:
            draw_text(surface, self.message, theme.get_font(15), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 6), "midbottom")
        if self.help_overlay:
            self._draw_help_overlay(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 220, 720, 440)
        Panel(rect, title="Base Help").draw(surface)
        lines = [
            "1) Draft a citizen from the left roster.",
            "2) Open Loadout and equip gear/tags.",
            "3) Deploy to mission briefing and begin run.",
            "Storage keeps gear; materials pouch is separate.",
            "Use H anytime to reopen help.",
            "Press any key to close.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(17), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(17), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 22
            y += 3
