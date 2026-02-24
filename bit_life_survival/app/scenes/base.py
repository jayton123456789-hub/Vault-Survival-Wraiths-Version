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

    def _draw_top_bar(self, app, surface: pygame.Surface, rect: pygame.Rect) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        mats = vault.materials
        line = (
            f"Vault Lv {vault.vault_level}   TAV {vault.tav}   Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}   "
            f"Storage Used {used}   Scrap {mats.get('scrap', 0)}   Cloth {mats.get('cloth', 0)}   "
            f"Plastic {mats.get('plastic', 0)}   Metal {mats.get('metal', 0)}"
        )
        draw_text(surface, line, theme.get_font(20, bold=True), theme.COLOR_TEXT, (rect.left + 12, rect.centery), "midleft")

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

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        root = app.screen.get_rect().inflate(-20, -20)
        rows = split_rows(root, [0.1, 0.78, 0.12], gap=10)
        body_cols = split_columns(rows[1], [0.28, 0.42, 0.30], gap=10)

        self._top_rect = rows[0]
        self._left_rect = body_cols[0]
        self._center_rect = body_cols[1]
        self._right_rect = body_cols[2]
        self._bottom_rect = rows[2]

        self.buttons.append(
            Button(
                pygame.Rect(self._left_rect.left + 12, self._left_rect.bottom - 50, self._left_rect.width - 24, 38),
                "Use The Claw",
                hotkey=pygame.K_u,
                on_click=lambda: self._claw(app),
                tooltip="Draft the next citizen for deployment.",
            )
        )
        self.buttons.append(
            Button(
                pygame.Rect(self._left_rect.left + 12, self._left_rect.bottom - 94, self._left_rect.width - 24, 36),
                "Draft Selected",
                hotkey=pygame.K_RETURN,
                on_click=lambda: self._draft_selected(app),
                tooltip="Draft the currently selected citizen in line.",
            )
        )
        citizen_list_rect = pygame.Rect(self._left_rect.left + 12, self._left_rect.top + 46, self._left_rect.width - 24, self._left_rect.height - 220)
        self.citizen_scroll = ScrollList(citizen_list_rect, row_height=24, on_select=self._on_select_citizen)
        self._refresh_citizen_rows(app)

        module_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 40, self._center_rect.width - 24, 44)
        modules = split_columns(module_row, [1, 1, 1], gap=8)
        self.buttons.append(Button(modules[0], "Storage", on_click=lambda: setattr(self, "selected_module", "storage"), tooltip="Browse stored gear."))
        self.buttons.append(Button(modules[1], "Crafting", on_click=lambda: setattr(self, "selected_module", "crafting"), tooltip="Build gear from materials."))
        self.buttons.append(Button(modules[2], "Drone Bay", on_click=lambda: setattr(self, "selected_module", "drone"), tooltip="Review recovery capability."))

        if self.selected_module == "storage":
            filter_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 94, self._center_rect.width - 24, 36)
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
            list_rect = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 136, self._center_rect.width - 24, self._center_rect.height - 148)
            self.storage_scroll = ScrollList(list_rect, row_height=28, on_select=self._on_storage_select)
            self._refresh_storage_rows(app)
        else:
            self.storage_scroll = None

        if self.selected_module == "crafting":
            start_y = self._center_rect.top + 110
            for recipe in app.content.recipes[:10]:
                row = pygame.Rect(self._center_rect.left + 12, start_y, self._center_rect.width - 24, 34)
                craftable, _ = can_craft(app.save_data.vault, recipe)
                self.buttons.append(
                    Button(
                        row,
                        f"Craft: {recipe.name}",
                        enabled=craftable,
                        on_click=lambda rid=recipe.id: self._craft_recipe(app, rid),
                        tooltip=recipe.description or f"Craft {recipe.name}.",
                    )
                )
                start_y += 38

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
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.message = "Vault help: U claw, L loadout, D deploy, S settings, H help."
            return
        if self.storage_scroll and self.storage_scroll.handle_event(event):
            return
        if self.citizen_scroll and self.citizen_scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_storage_module(self, app, surface: pygame.Surface) -> None:
        materials_rect = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 94, self._center_rect.width - 24, 36)
        if self.selected_module == "storage":
            material_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 54, self._center_rect.width - 24, 30)
            cols = split_columns(material_row, [1, 1, 1, 1], gap=8)
            for col, mid in zip(cols, MATERIAL_IDS):
                pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=6)
                pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=1, border_radius=6)
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
                "Materials pouch does not count toward Storage Used.",
                theme.get_font(14),
                theme.COLOR_TEXT_MUTED,
                (materials_rect.left, materials_rect.bottom + 6),
            )
        elif self.selected_module == "crafting":
            draw_text(surface, "Crafting recipes (greyed-out = missing materials).", theme.get_font(16), theme.COLOR_TEXT_MUTED, (materials_rect.left, materials_rect.top))
            draw_text(
                surface,
                "Materials",
                theme.get_font(15, bold=True),
                theme.COLOR_TEXT,
                (materials_rect.left, materials_rect.top + 24),
            )
            y = materials_rect.top + 46
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

        surface.fill(theme.COLOR_BG)
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._left_rect, title="Citizen Line").draw(surface)
        Panel(self._center_rect, title="Vault Modules").draw(surface)
        Panel(self._right_rect, title="Details").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface, self._top_rect)
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        queue = app.save_data.vault.citizen_queue[:5]
        y = self._left_rect.top + 48
        draw_text(surface, f"Queued Citizens: {len(app.save_data.vault.citizen_queue)}", theme.get_font(18), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 30
        if self.citizen_scroll:
            self.citizen_scroll.draw(surface)
        selected = self._selected_citizen(app)
        y = self._left_rect.bottom - 170
        draw_text(surface, "Citizen Details", theme.get_font(16, bold=True), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 22
        if selected:
            draw_text(surface, f"{selected.name}", theme.get_font(16, bold=True), theme.COLOR_SUCCESS, (self._left_rect.left + 12, y))
            y += 20
            draw_text(surface, selected.quirk, theme.get_font(14), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))
            y += 20
            kit = ", ".join(f"{item} x{qty}" for item, qty in sorted(selected.kit.items())) or "None"
            for line in wrap_text(f"Kit: {kit}", theme.get_font(13), self._left_rect.width - 24):
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
