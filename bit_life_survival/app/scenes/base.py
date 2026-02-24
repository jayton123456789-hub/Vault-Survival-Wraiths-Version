from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
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

    def _draw_top_bar(self, app, surface: pygame.Surface, rect: pygame.Rect) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        mats = vault.materials
        first_line = (
            f"Vault Lv {vault.vault_level}     TAV {vault.tav}     Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}     "
            f"Storage Used {used}"
        )
        second_line = (
            f"Scrap {mats.get('scrap', 0)}     Cloth {mats.get('cloth', 0)}     "
            f"Plastic {mats.get('plastic', 0)}     Metal {mats.get('metal', 0)}"
        )
        draw_text(surface, first_line, theme.get_font(19, bold=True), theme.COLOR_TEXT, (rect.left + 14, rect.top + 42))
        draw_text(surface, second_line, theme.get_font(19, bold=True), theme.COLOR_TEXT, (rect.left + 14, rect.top + 66))

    def _deploy(self, app) -> None:
        if app.save_data.vault.current_citizen is None:
            self.message = "Use The Claw to draft a citizen first."
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
        self.message = f"Drafted {drafted.name}."

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
        self._citizen_rows = [f"{idx + 1:02d}. {citizen.name}" for idx, citizen in enumerate(queue)]
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
            if not item:
                continue
            if not self._storage_matches_filters(item):
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

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        root = app.screen.get_rect().inflate(-20, -20)
        rows = split_rows(root, [0.14, 0.74, 0.12], gap=10)
        body_cols = split_columns(rows[1], [0.28, 0.42, 0.30], gap=10)

        self._top_rect = rows[0]
        self._left_rect = body_cols[0]
        self._center_rect = body_cols[1]
        self._right_rect = body_cols[2]
        self._bottom_rect = rows[2]

        claw_rect = pygame.Rect(self._left_rect.left + 12, self._left_rect.bottom - 50, self._left_rect.width - 24, 38)
        draft_rect = pygame.Rect(self._left_rect.left + 12, self._left_rect.bottom - 94, self._left_rect.width - 24, 36)
        self.buttons.append(
            Button(
                claw_rect,
                "Use The Claw",
                hotkey=pygame.K_u,
                on_click=lambda: self._claw(app),
                tooltip="Draft the next citizen for deployment.",
            )
        )
        self.buttons.append(
            Button(
                draft_rect,
                "Draft Selected",
                hotkey=pygame.K_RETURN,
                on_click=lambda: self._draft_selected(app),
                tooltip="Draft the currently selected citizen in line.",
            )
        )
        citizen_list_rect = pygame.Rect(self._left_rect.left + 12, self._left_rect.top + 46, self._left_rect.width - 24, self._left_rect.height - 244)
        self.citizen_scroll = ScrollList(citizen_list_rect, row_height=24, on_select=self._on_select_citizen)
        self._refresh_citizen_rows(app)
        self._citizen_detail_rect = pygame.Rect(
            self._left_rect.left + 12,
            citizen_list_rect.bottom + 8,
            self._left_rect.width - 24,
            max(52, draft_rect.top - (citizen_list_rect.bottom + 16)),
        )

        module_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 40, self._center_rect.width - 24, 44)
        modules = split_columns(module_row, [1, 1, 1], gap=8)
        self.buttons.append(Button(modules[0], "Storage", on_click=lambda: setattr(self, "selected_module", "storage"), tooltip="Browse stored gear."))
        self.buttons.append(Button(modules[1], "Crafting", on_click=lambda: setattr(self, "selected_module", "crafting"), tooltip="Build gear from materials."))
        self.buttons.append(Button(modules[2], "Drone Bay", on_click=lambda: setattr(self, "selected_module", "drone"), tooltip="Review recovery capability."))

        if self.selected_module == "storage":
            filter_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 128, self._center_rect.width - 24, 36)
            filter_cols = split_columns(filter_row, [1, 1], gap=8)
            self.buttons.append(
                Button(
                    filter_cols[0],
                    f"Slot: {self.selected_slot_filter}",
                    on_click=lambda: self._cycle_storage_filter(app, "slot"),
                    tooltip="Filter stored gear by slot type.",
                )
            )
            self.buttons.append(
                Button(
                    filter_cols[1],
                    f"Rarity: {self.selected_rarity_filter}",
                    on_click=lambda: self._cycle_storage_filter(app, "rarity"),
                    tooltip="Filter stored gear by rarity.",
                )
            )
            list_rect = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 172, self._center_rect.width - 24, self._center_rect.height - 184)
            self.storage_scroll = ScrollList(list_rect, row_height=28, on_select=self._on_storage_select)
            self._refresh_storage_rows(app)
            self._storage_list_rect = list_rect
        else:
            self.storage_scroll = None
            self._storage_list_rect = None

        if self.selected_module == "crafting":
            self.crafting_scroll = ScrollList(
                pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 110, self._center_rect.width - 24, self._center_rect.height - 172),
                row_height=30,
                on_select=self._on_recipe_select,
            )
            self._refresh_recipe_rows(app)
            craft_button_rect = pygame.Rect(self._center_rect.left + 12, self._center_rect.bottom - 54, self._center_rect.width - 24, 36)
            recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
            craftable = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            self.buttons.append(
                Button(
                    craft_button_rect,
                    "Craft Selected",
                    hotkey=pygame.K_RETURN,
                    enabled=craftable,
                    on_click=lambda: self._craft_selected(app),
                    tooltip="Craft the selected recipe if requirements are met.",
                )
            )
        else:
            self.crafting_scroll = None

        bottom_cols = split_columns(
            pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top + 8, self._bottom_rect.width - 16, self._bottom_rect.height - 16),
            [1, 1, 1, 1],
            gap=10,
        )
        self.buttons.append(Button(bottom_cols[0], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app), tooltip="Choose equipment for the next run."))
        self.buttons.append(Button(bottom_cols[1], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), tooltip="Start a run with current draft and loadout."))
        self.buttons.append(Button(bottom_cols[2], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Open gameplay and video settings."))
        self.buttons.append(Button(bottom_cols[3], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._main_menu(app), tooltip="Return to the front menu."))

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

    def _draw_storage_module(self, app, surface: pygame.Surface) -> None:
        materials_rect = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 86, self._center_rect.width - 24, 34)
        if self.selected_module == "storage":
            material_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 86, self._center_rect.width - 24, 34)
            cols = split_columns(material_row, [1, 1, 1, 1], gap=8)
            for col, mid in zip(cols, MATERIAL_IDS):
                pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=2)
                pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=2, border_radius=2)
                draw_text(
                    surface,
                    f"{mid.title()}: {app.save_data.vault.materials.get(mid, 0)}",
                    theme.get_font(14, bold=True),
                    theme.COLOR_TEXT,
                    col.center,
                    "center",
                )
            if self.storage_scroll:
                self.storage_scroll.draw(surface)
            draw_text(
                surface,
                "Materials do not count toward storage capacity.",
                theme.get_font(14),
                theme.COLOR_TEXT_MUTED,
                (materials_rect.left, materials_rect.bottom + 8),
            )
        elif self.selected_module == "crafting":
            draw_text(surface, "Crafting recipes (select to view requirements).", theme.get_font(16), theme.COLOR_TEXT_MUTED, (materials_rect.left, materials_rect.top))
            if self.crafting_scroll:
                self.crafting_scroll.draw(surface)
            y = materials_rect.top + 28
            for mid in MATERIAL_IDS:
                draw_text(surface, f"{mid.title()}: {app.save_data.vault.materials.get(mid, 0)}", theme.get_font(15), theme.COLOR_TEXT_MUTED, (materials_rect.left, y))
                y += 20
        else:
            level = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
            lines = [
                f"Drone Bay Level: {level}",
                "Higher levels improve recovery chance.",
                "Upgrade paths arrive in later phases.",
            ]
            yy = materials_rect.top
            for line in lines:
                draw_text(surface, line, theme.get_font(16), theme.COLOR_TEXT, (materials_rect.left, yy))
                yy += 24

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        if self.selected_module == "crafting":
            y = self._right_rect.top + 50
            draw_text(surface, "Crafting Detail", theme.get_font(20, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
            y += 30
            if not self.selected_recipe_id:
                draw_text(surface, "Select a recipe to inspect requirements.", theme.get_font(15), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 12, y))
                return
            recipe = app.content.recipe_by_id[self.selected_recipe_id]
            craftable, requirements = can_craft(app.save_data.vault, recipe)
            draw_text(surface, recipe.name, theme.get_font(18, bold=True), theme.COLOR_ACCENT, (self._right_rect.left + 12, y))
            y += 24
            if recipe.description:
                for line in wrap_text(recipe.description, theme.get_font(14), self._right_rect.width - 24):
                    draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 12, y))
                    y += 18
            y += 6
            draw_text(surface, "Requirements", theme.get_font(16, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
            y += 22
            for material_id, (have, need) in requirements.items():
                okay = have >= need
                color = theme.COLOR_SUCCESS if okay else theme.COLOR_WARNING
                draw_text(surface, f"{material_id.title()}: {have} / {need}", theme.get_font(15), color, (self._right_rect.left + 12, y))
                y += 20
            y += 10
            out_item = app.content.item_by_id.get(recipe.output_item)
            out_name = out_item.name if out_item else recipe.output_item
            draw_text(surface, f"Output: {out_name} x{recipe.output_qty}", theme.get_font(16), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
            y += 22
            draw_text(
                surface,
                "Status: Craftable" if craftable else "Status: Missing materials",
                theme.get_font(16, bold=True),
                theme.COLOR_SUCCESS if craftable else theme.COLOR_WARNING,
                (self._right_rect.left + 12, y),
            )
            return

        if self.selected_module == "storage" and self.selected_storage_item_id:
            item = app.content.item_by_id.get(self.selected_storage_item_id)
            if item:
                y = self._right_rect.top + 50
                draw_text(surface, item.name, theme.get_font(20, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
                y += 26
                draw_text(surface, f"ID: {item.id}", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 12, y))
                y += 22
                draw_text(surface, f"Slot: {item.slot} | Rarity: {item.rarity}", theme.get_font(15), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
                y += 22
                draw_text(surface, f"Stored Qty: {app.save_data.vault.storage.get(item.id, 0)}", theme.get_font(15), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
                y += 24
                tags = ", ".join(item.tags) if item.tags else "-"
                for line in wrap_text(f"Tags: {tags}", theme.get_font(14), self._right_rect.width - 24):
                    draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 12, y))
                    y += 18
                y += 6
                mods = item.modifiers.model_dump(mode="python", exclude_none=True)
                if not mods:
                    draw_text(surface, "No stat modifiers.", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 12, y))
                else:
                    for key, value in mods.items():
                        draw_text(surface, f"{key}: {value:+.2f}" if isinstance(value, float) else f"{key}: {value}", theme.get_font(14), theme.COLOR_TEXT, (self._right_rect.left + 12, y))
                        y += 18
                return

        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        yy = self._right_rect.top + 50
        draw_text(surface, "Loadout Preview", theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 12, yy))
        yy += 26
        for slot_name, item_id in app.current_loadout.model_dump(mode="python").items():
            label = item_id or "-"
            draw_text(surface, f"{slot_name}: {label}", theme.get_font(15), theme.COLOR_TEXT_MUTED, (self._right_rect.left + 14, yy))
            yy += 20
        yy += 8
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        for line in wrap_text(f"Tags: {tags}", theme.get_font(15), self._right_rect.width - 24):
            draw_text(surface, line, theme.get_font(15), theme.COLOR_TEXT, (self._right_rect.left + 12, yy))
            yy += 20
        stats = [
            f"Speed {summary['speed_bonus']:+.2f}",
            f"Carry {summary['carry_bonus']:+.1f}",
            f"Injury Resist {summary['injury_resist']*100:.0f}%",
            f"Noise {summary['noise']:+.2f}",
        ]
        for line in stats:
            draw_text(surface, line, theme.get_font(15), theme.COLOR_TEXT, (self._right_rect.left + 12, yy))
            yy += 20

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
        Panel(self._right_rect, title="Details").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface, self._top_rect)
        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            if button.text == "Craft Selected":
                recipe = app.content.recipe_by_id.get(self.selected_recipe_id) if self.selected_recipe_id else None
                button.enabled = bool(recipe and can_craft(app.save_data.vault, recipe)[0])
            button.draw(surface, mouse_pos)

        y = self._left_rect.top + 48
        draw_text(surface, f"Queued Citizens: {len(app.save_data.vault.citizen_queue)}", theme.get_font(18), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 30
        if self.citizen_scroll:
            self.citizen_scroll.draw(surface)
        selected = self._selected_citizen(app)
        y = self._citizen_detail_rect.top
        draw_text(surface, "Citizen Details", theme.get_font(16, bold=True), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 22
        if selected:
            draw_text(surface, f"{selected.name}", theme.get_font(16, bold=True), theme.COLOR_SUCCESS, (self._left_rect.left + 12, y))
            y += 20
            draw_text(surface, selected.quirk, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))
            y += 20
            kit = ", ".join(f"{item} x{qty}" for item, qty in sorted(selected.kit.items())) or "None"
            for line in wrap_text(f"Kit: {kit}", theme.get_font(13), self._left_rect.width - 24)[:3]:
                draw_text(surface, line, theme.get_font(13), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))
                y += 16
        else:
            draw_text(surface, "Select a citizen to inspect kit.", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))
            y += 20
        current = app.save_data.vault.current_citizen
        draw_text(surface, "Current Draft:", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 24
        if current:
            draw_text(surface, f"{current.name} - {current.quirk}", theme.get_font(16), theme.COLOR_SUCCESS, (self._left_rect.left + 12, y))
        else:
            draw_text(surface, "None", theme.get_font(16), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))

        self._draw_storage_module(app, surface)
        self._draw_right_panel(app, surface)
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
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 220, 720, 440)
        Panel(rect, title="Base Help").draw(surface)
        lines = [
            "The Claw drafts one citizen into the current run slot.",
            "Deploy moves to briefing, then starts the run.",
            "Loadout tags unlock stronger event options during runs.",
            "Materials pouch stores scrap/cloth/plastic/metal outside gear storage limits.",
            "Crafting consumes materials and produces gear for storage.",
            "Retreat during a run ends early and applies drone recovery penalties.",
            "Press any key to close this help screen.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(17), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(17), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 22
            y += 3
