from __future__ import annotations

import pygame

from bit_life_survival.app.services.loadout_planner import RUN_SLOTS, choose_best_for_slot, format_choice_reason
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.overlays.tutorial import TutorialOverlay, TutorialStep
from bit_life_survival.app.ui.widgets import (
    Button,
    CommandStrip,
    EmptyState,
    Panel,
    ScrollList,
    SectionCard,
    StatChip,
    clamp_wrapped_lines,
    draw_text,
    draw_tooltip_bar,
    hovered_tooltip,
    wrap_text,
)
from bit_life_survival.core.crafting import (
    apply_milestone_blueprints,
    can_craft,
    craft,
    locked_recipes,
    unlocked_recipes,
)
from bit_life_survival.core.models import GameState, Recipe
from bit_life_survival.core.persistence import get_active_deploy_citizen, store_item, take_item
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene

TAB_KEYS = ("loadout", "equippable", "craftables", "storage", "crafting")
SLOT_FILTER_VALUES = ["all", "pack", "armor", "vehicle", "utility", "faction", "consumable"]
RARITY_FILTER_VALUES = ["all", "common", "uncommon", "rare", "legendary"]
MATERIAL_IDS = ("scrap", "cloth", "plastic", "metal")
EQUIPPABLE_SLOTS = {"pack", "armor", "vehicle", "utility", "faction"}


class OperationsScene(Scene):
    def __init__(self, initial_tab: str = "loadout") -> None:
        self.tab = initial_tab if initial_tab in TAB_KEYS else "loadout"
        self.buttons: list[Button] = []
        self._tab_buttons: dict[str, Button] = {}
        self._slot_buttons: dict[str, Button] = {}
        self._action_buttons: dict[str, Button] = {}
        self._last_size: tuple[int, int] | None = None
        self._rows: list[tuple[str, int]] = []
        self._recipes: list[Recipe] = []
        self._recipe_rows: list[tuple[Recipe, bool]] = []
        self._recipe_output_ids: set[str] = set()
        self._scroll: ScrollList | None = None
        self.message = ""
        self.help_overlay = False
        self.selected_slot_filter = "all"
        self.selected_rarity_filter = "all"
        self.selected_item_id: str | None = None
        self.selected_recipe_id: str | None = None
        self.active_slot: str | None = None
        self._vault_assistant: TutorialOverlay | None = None
        self._assistant_stage: int | None = None

        self._panel_rect = pygame.Rect(0, 0, 0, 0)
        self._tab_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._status_rect = pygame.Rect(0, 0, 0, 0)
        self._tooltip_rect = pygame.Rect(0, 0, 0, 0)
        self._footer_rect = pygame.Rect(0, 0, 0, 0)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)
        self._filters_rect = pygame.Rect(0, 0, 0, 0)
        self._list_rect = pygame.Rect(0, 0, 0, 0)
        self._detail_rect = pygame.Rect(0, 0, 0, 0)
        self._summary_rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def _assistant_session_flags(app) -> set[str]:
        flags = getattr(app, "_vault_assistant_seen", None)
        if not isinstance(flags, set):
            flags = set()
            setattr(app, "_vault_assistant_seen", flags)
        return flags

    def on_enter(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault) if app.save_data else None
        if citizen is not None:
            app.current_loadout = citizen.loadout.model_copy(deep=True)
        unlocked_now = apply_milestone_blueprints(app.save_data.vault) if app.save_data else []
        if unlocked_now:
            self.message = f"Unlocked recipes: {', '.join(unlocked_now[:2])}"
            app.save_current_slot()
        self._refresh_rows(app)
        self._begin_vault_assistant(app)

    def _begin_vault_assistant(self, app) -> None:
        if not hasattr(app, "settings") or not isinstance(app.settings, dict):
            return
        gameplay = app.settings.setdefault("gameplay", {})
        if not bool(gameplay.get("vault_assistant_enabled", True)):
            return
        stage = int(gameplay.get("vault_assistant_stage", 0))
        completed = bool(gameplay.get("vault_assistant_completed", False))
        if completed or stage != 1:
            return
        if "stage_1" in self._assistant_session_flags(app):
            return
        self._assistant_stage = stage
        self._vault_assistant = TutorialOverlay(
            [
                TutorialStep(
                    title="Loadout Slots",
                    body="Click a loadout slot to focus it. Item list auto-filters to compatible gear.",
                    target_rect_getter=lambda: self._right_rect,
                ),
                TutorialStep(
                    title="Equip Flow",
                    body="Choose an item from the left, then press Equip Selected. Equip Best works on focused slot too.",
                    target_rect_getter=lambda: self._footer_rect,
                ),
                TutorialStep(
                    title="Crafting Value",
                    body="Crafting recipes unlock gradually. Recipe detail explains purpose and run impact.",
                    target_rect_getter=lambda: self._tab_rect,
                ),
            ],
            series_label="Vault Assistant (Run 2/3)",
            avoid_rect_getters=[
                lambda: self._footer_rect,
            ],
        )

    def _finish_assistant_stage(self, app, skipped: bool = False) -> None:
        if self._assistant_stage is None:
            return
        if not hasattr(app, "settings") or not isinstance(app.settings, dict):
            self._assistant_stage = None
            self._vault_assistant = None
            return
        gameplay = app.settings.setdefault("gameplay", {})
        if skipped:
            gameplay["vault_assistant_completed"] = True
            gameplay["vault_assistant_stage"] = 3
        else:
            gameplay["vault_assistant_stage"] = 2
        self._assistant_session_flags(app).add("stage_1")
        if hasattr(app, "save_settings"):
            app.save_settings()
        self._assistant_stage = None
        self._vault_assistant = None

    def _sync_citizen_loadout(self, app) -> None:
        citizen = get_active_deploy_citizen(app.save_data.vault) if app.save_data else None
        if citizen is not None:
            citizen.loadout = app.current_loadout.model_copy(deep=True)

    def _allowed_slot(self, run_slot: str) -> str:
        return "utility" if run_slot in {"utility1", "utility2"} else run_slot

    def _is_equippable(self, item) -> bool:
        return item.slot in EQUIPPABLE_SLOTS

    def _is_craftable_item(self, item_id: str, item) -> bool:
        return item_id in self._recipe_output_ids or item.slot == "consumable"

    def _item_matches_filter(self, item) -> bool:
        if self.selected_slot_filter != "all" and item.slot != self.selected_slot_filter:
            return False
        if self.selected_rarity_filter != "all" and item.rarity != self.selected_rarity_filter:
            return False
        return True

    def _item_visible_for_tab(self, item_id: str, item) -> bool:
        if self.tab == "loadout":
            return self._is_equippable(item)
        if self.tab == "equippable":
            return self._is_equippable(item)
        if self.tab == "craftables":
            return self._is_craftable_item(item_id, item)
        if self.tab == "storage":
            return True
        return False

    @staticmethod
    def _short_text(value: str, limit: int) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        if limit <= 3:
            return text[:limit]
        return f"{text[: limit - 3]}..."

    def _refresh_rows(self, app) -> None:
        newly_unlocked = apply_milestone_blueprints(app.save_data.vault)
        if newly_unlocked:
            self.message = f"Unlocked recipes: {', '.join(newly_unlocked[:2])}"
            if hasattr(app, "save_current_slot"):
                app.save_current_slot()
        unlocked = unlocked_recipes(app.save_data.vault, app.content.recipes)
        locked = locked_recipes(app.save_data.vault, app.content.recipes)
        unlocked.sort(key=lambda recipe: ((recipe.unlock_tav or 0), recipe.name))
        locked.sort(key=lambda recipe: ((recipe.unlock_tav or 0), recipe.name))
        self._recipes = unlocked
        self._recipe_rows = [(recipe, True) for recipe in unlocked] + [(recipe, False) for recipe in locked]
        self._recipe_output_ids = {recipe.output_item for recipe in app.content.recipes}

        rows: list[tuple[str, int]] = []
        for item_id, qty in sorted(app.save_data.vault.storage.items()):
            if qty <= 0:
                continue
            item = app.content.item_by_id.get(item_id)
            if not item:
                continue
            if self.tab != "crafting":
                if not self._item_visible_for_tab(item_id, item):
                    continue
                if not self._item_matches_filter(item):
                    continue
                rows.append((item_id, qty))
        self._rows = rows

        if self._scroll:
            if self.tab == "crafting":
                labels = [recipe.name if unlocked_recipe else f"{recipe.name} [LOCKED]" for recipe, unlocked_recipe in self._recipe_rows]
                self._scroll.set_items(labels)
            else:
                self._scroll.set_items([f"{app.content.item_by_id[item_id].name}  x{qty}" for item_id, qty in rows])

        if self.tab == "crafting":
            recipe_ids = {recipe.id for recipe, _ in self._recipe_rows}
            if self.selected_recipe_id not in recipe_ids:
                self.selected_recipe_id = self._recipe_rows[0][0].id if self._recipe_rows else None
        else:
            if self.selected_item_id not in {item_id for item_id, _ in rows}:
                self.selected_item_id = rows[0][0] if rows else None

    def _on_select_row(self, index: int) -> None:
        if self.tab == "crafting":
            if 0 <= index < len(self._recipe_rows):
                self.selected_recipe_id = self._recipe_rows[index][0].id
            return
        if 0 <= index < len(self._rows):
            self.selected_item_id = self._rows[index][0]

    def _cycle_filter(self, app, which: str) -> None:
        if which == "slot":
            idx = SLOT_FILTER_VALUES.index(self.selected_slot_filter)
            self.selected_slot_filter = SLOT_FILTER_VALUES[(idx + 1) % len(SLOT_FILTER_VALUES)]
        else:
            idx = RARITY_FILTER_VALUES.index(self.selected_rarity_filter)
            self.selected_rarity_filter = RARITY_FILTER_VALUES[(idx + 1) % len(RARITY_FILTER_VALUES)]
        self._refresh_rows(app)
        self._last_size = None

    def _set_tab(self, app, tab: str) -> None:
        self.tab = tab
        self.message = ""
        self.active_slot = None
        self._refresh_rows(app)
        self._last_size = None

    def _focus_slot(self, app, run_slot: str) -> None:
        self.active_slot = run_slot
        desired_filter = self._allowed_slot(run_slot)
        if self.selected_slot_filter != desired_filter:
            self.selected_slot_filter = desired_filter
            self._refresh_rows(app)
            self._last_size = None
        self.message = f"Focused {run_slot}. Choose an item then press Equip Selected."

    def _equip_item_to_slot(self, app, run_slot: str, item_id: str) -> bool:
        item = app.content.item_by_id.get(item_id)
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
        app.save_current_slot()
        self._refresh_rows(app)
        self.message = f"Equipped {item.name} to {run_slot}."
        return True

    def _equip_selected(self, app) -> None:
        if self.active_slot is None:
            self.message = "Focus a loadout slot first."
            return
        if self.selected_item_id is None:
            self.message = "Select an item from the list first."
            return
        if self._equip_item_to_slot(app, self.active_slot, self.selected_item_id):
            return

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
            app.save_current_slot()
            self._refresh_rows(app)
            return
        self._equip_all(app)

    def _equip_all(self, app) -> None:
        self._unequip_all(app)
        reserved: dict[str, int] = {}
        reason_lines: list[str] = []
        for run_slot in RUN_SLOTS:
            choice = choose_best_for_slot(app.content, app.save_data.vault.storage, run_slot, reserved)
            if not choice:
                continue
            if not take_item(app.save_data.vault, choice.item_id, 1):
                continue
            reserved[choice.item_id] = reserved.get(choice.item_id, 0) + 1
            setattr(app.current_loadout, run_slot, choice.item_id)
            reason_lines.append(format_choice_reason(app.content, choice))
        self._sync_citizen_loadout(app)
        app.save_current_slot()
        self._refresh_rows(app)
        self.message = " | ".join(reason_lines[:2]) if reason_lines else "No available gear to auto-equip."

    def _craft_selected(self, app) -> None:
        if self.tab != "crafting":
            self.message = "Switch to Crafting tab to craft recipes."
            return
        if not self.selected_recipe_id:
            self.message = "No recipe selected."
            return
        recipe = app.content.recipe_by_id.get(self.selected_recipe_id)
        if not recipe:
            self.message = "Recipe missing."
            return
        if recipe.id not in app.save_data.vault.blueprints:
            unlock_at = recipe.unlock_tav if recipe.unlock_tav is not None else 0
            self.message = f"Recipe locked. Reach TAV {unlock_at} or find a blueprint."
            return
        if not craft(app.save_data.vault, recipe):
            self.message = "Missing materials for that recipe."
            return
        app.save_current_slot()
        self._refresh_rows(app)
        self.message = f"Crafted {app.content.item_by_id[recipe.output_item].name} x{recipe.output_qty}."

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
        if self._last_size == app.screen.get_size() and self.buttons and self._scroll:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._tab_buttons.clear()
        self._slot_buttons.clear()
        self._action_buttons.clear()

        self._panel_rect = app.screen.get_rect().inflate(-16, -16)
        inner = pygame.Rect(self._panel_rect.left + 12, self._panel_rect.top + 36, self._panel_rect.width - 24, self._panel_rect.height - 48)
        self._tab_rect, body, status_row, self._footer_rect = split_rows(inner, [0.09, 0.72, 0.06, 0.13], gap=8)
        self._status_rect, self._tooltip_rect = split_columns(status_row, [0.58, 0.42], gap=8)
        self._left_rect, self._right_rect = split_columns(body, [0.58, 0.42], gap=8)

        tab_cols = split_columns(self._tab_rect, [1, 1, 1, 1, 1], gap=8)
        for rect, tab_key in zip(tab_cols, TAB_KEYS):
            label = tab_key.title()
            button = Button(rect, label, on_click=lambda t=tab_key: self._set_tab(app, t), allow_skin=False, tooltip=f"Switch to {label}.")
            self._tab_buttons[tab_key] = button
            self.buttons.append(button)

        left_inner = pygame.Rect(self._left_rect.left + 8, self._left_rect.top + 34, self._left_rect.width - 16, self._left_rect.height - 42)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)
        self._filters_rect = pygame.Rect(0, 0, 0, 0)
        if self.tab == "storage":
            self._materials_rect, self._filters_rect, self._list_rect = split_rows(left_inner, [0.20, 0.12, 0.68], gap=8)
        elif self.tab == "crafting":
            self._list_rect = left_inner
        else:
            self._filters_rect, self._list_rect = split_rows(left_inner, [0.12, 0.88], gap=8)

        if self.tab != "crafting":
            filter_cols = split_columns(self._filters_rect, [1, 1], gap=8)
            self.buttons.append(
                Button(
                    filter_cols[0],
                    f"Slot: {self.selected_slot_filter}",
                    on_click=lambda: self._cycle_filter(app, "slot"),
                    allow_skin=False,
                    tooltip="Cycle slot filter.",
                )
            )
            self.buttons.append(
                Button(
                    filter_cols[1],
                    f"Rarity: {self.selected_rarity_filter}",
                    on_click=lambda: self._cycle_filter(app, "rarity"),
                    allow_skin=False,
                    tooltip="Cycle rarity filter.",
                )
            )

        self._scroll = ScrollList(self._list_rect, row_height=30, on_select=self._on_select_row)
        self._scroll.row_renderer = self._draw_recipe_row if self.tab == "crafting" else None
        self._refresh_rows(app)

        self._detail_rect = pygame.Rect(self._right_rect.left + 8, self._right_rect.top + 34, self._right_rect.width - 16, self._right_rect.height - 42)
        self._summary_rect = self._detail_rect
        if self.tab == "loadout":
            slot_area, self._summary_rect = split_rows(self._detail_rect, [0.60, 0.40], gap=8)
            slot_rows = split_rows(slot_area, [1, 1], gap=8)
            slot_grid = [*split_columns(slot_rows[0], [1, 1, 1], gap=8), *split_columns(slot_rows[1], [1, 1, 1], gap=8)]
            for rect, run_slot in zip(slot_grid, RUN_SLOTS):
                button = Button(rect, run_slot.upper(), on_click=lambda s=run_slot: self._focus_slot(app, s), allow_skin=False, tooltip=f"Focus {run_slot} and filter compatible items.")
                button.text_align = "center"
                button.text_fit_mode = "ellipsis"
                button.max_font_role = "body"
                self._slot_buttons[run_slot] = button
                self.buttons.append(button)

        action_cols = split_columns(self._footer_rect, [1, 1, 1, 1, 1, 1], gap=8)
        self._action_buttons["back"] = Button(action_cols[0], "Back", hotkey=pygame.K_ESCAPE, on_click=lambda: self._back(app), skin_key="back", skin_render_mode="frame_text", max_font_role="section", tooltip="Return to vault base.")
        self._action_buttons["deploy"] = Button(action_cols[1], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), skin_key="deploy", skin_render_mode="frame_text", max_font_role="section", tooltip="Begin run briefing.")
        self._action_buttons["equip_selected"] = Button(action_cols[2], "Equip Selected", hotkey=pygame.K_e, on_click=lambda: self._equip_selected(app), allow_skin=False, text_align="left", text_fit_mode="ellipsis", max_font_role="section", tooltip="Equip selected item to focused slot.")
        self._action_buttons["equip_best"] = Button(action_cols[3], "Equip Best", hotkey=pygame.K_b, on_click=lambda: self._equip_best(app), skin_key="equip_best", skin_render_mode="frame_text", max_font_role="section", tooltip="Auto-equip best slot or active slot.")
        self._action_buttons["equip_all"] = Button(action_cols[4], "Equip All", hotkey=pygame.K_a, on_click=lambda: self._equip_all(app), skin_key="equip_all", skin_render_mode="frame_text", max_font_role="section", tooltip="Fill all loadout slots.")
        self._action_buttons["craft"] = Button(action_cols[5], "Craft", on_click=lambda: self._craft_selected(app), skin_key="craft", skin_render_mode="frame_text", max_font_role="section", tooltip="Craft selected recipe.")
        self._action_buttons["craft"].enabled = self.tab == "crafting"
        self._action_buttons["equip_selected"].enabled = self.tab == "loadout"
        self._action_buttons["equip_best"].enabled = self.tab == "loadout"
        self._action_buttons["equip_all"].enabled = self.tab == "loadout"
        self.buttons.extend(self._action_buttons.values())

    def _draw_recipe_row(self, surface: pygame.Surface, row_rect: pygame.Rect, index: int, text: str, selected: bool, now_s: float) -> None:
        if not (0 <= index < len(self._recipe_rows)):
            draw_text(surface, text, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT, (row_rect.left + 8, row_rect.centery), "midleft")
            return
        recipe, unlocked = self._recipe_rows[index]
        color = theme.COLOR_TEXT if unlocked else theme.COLOR_TEXT_MUTED
        if not unlocked and not selected:
            pygame.draw.rect(surface, theme.COLOR_PROGRESS_BG, row_rect, border_radius=2)
        label = recipe.name if unlocked else f"{recipe.name} [LOCKED]"
        draw_text(surface, label, theme.get_font(theme.FONT_SIZE_BODY), color, (row_rect.left + 8, row_rect.centery), "midleft")

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if self._vault_assistant and self._vault_assistant.visible:
            result = self._vault_assistant.handle_event(event)
            if result == "done":
                self._finish_assistant_stage(app, skipped=False)
            elif result == "skip":
                self._finish_assistant_stage(app, skipped=True)
            return
        if self.help_overlay:
            if event.type in {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN}:
                self.help_overlay = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.help_overlay = True
            return
        if self._scroll and self._scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_left_panel(self, app, surface: pygame.Surface) -> None:
        title = {
            "loadout": "Loadout Items",
            "equippable": "Equippable Gear",
            "craftables": "Craftable Items",
            "storage": "Storage",
            "crafting": "Crafting Recipes",
        }[self.tab]
        body = SectionCard(self._left_rect, title).draw(surface)

        if self.tab == "storage":
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._materials_rect, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, self._materials_rect, width=2, border_radius=2)
            draw_text(
                surface,
                "Materials",
                theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"),
                theme.COLOR_TEXT,
                (self._materials_rect.left + 8, self._materials_rect.top + 4),
            )
            material_row = pygame.Rect(self._materials_rect.left + 8, self._materials_rect.top + 24, self._materials_rect.width - 16, self._materials_rect.height - 32)
            material_cols = split_columns(material_row, [1, 1, 1, 1], gap=6)
            for col, material_id in zip(material_cols, MATERIAL_IDS):
                StatChip(col, material_id.title(), str(app.save_data.vault.materials.get(material_id, 0))).draw(surface)

        if self._scroll and self._rows:
            self._scroll.draw(surface)
        elif self.tab != "crafting":
            EmptyState(
                pygame.Rect(body.left, max(body.top + 6, self._list_rect.top), body.width, max(44, self._list_rect.height - 10)),
                "No Items",
                "No inventory entries match the current filters.",
            ).draw(surface)
        elif self._scroll:
            self._scroll.draw(surface)

    def _draw_item_detail(self, app, surface: pygame.Surface) -> None:
        if not self.selected_item_id:
            EmptyState(self._detail_rect, "No Selection", "Choose an item from the left panel to inspect stats and effects.").draw(surface)
            return
        item = app.content.item_by_id.get(self.selected_item_id)
        if not item:
            EmptyState(self._detail_rect, "Missing Item", "The selected item no longer exists in content data.").draw(surface)
            return
        y = self._detail_rect.top + 8
        bottom = self._detail_rect.bottom
        draw_text(surface, item.name, theme.get_font(theme.FONT_SIZE_TITLE, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
        y += 24
        draw_text(surface, f"{item.rarity} | {item.slot}", theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
        y += 18
        tags = ", ".join(item.tags) if item.tags else "-"
        for line in wrap_text(f"Tags: {tags}", theme.get_font(theme.FONT_SIZE_BODY), self._detail_rect.width - 20):
            if y + theme.get_font(theme.FONT_SIZE_BODY).get_linesize() > bottom:
                break
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
            y += theme.FONT_SIZE_BODY + 2
        y += 4
        mods = item.modifiers.model_dump(mode="python", exclude_none=True)
        if not mods:
            draw_text(surface, "No modifiers.", theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
            return
        for key, value in mods.items():
            text = f"{key}: {value:+.2f}" if isinstance(value, float) else f"{key}: {value}"
            if y + theme.get_font(theme.FONT_SIZE_BODY).get_linesize() > bottom:
                break
            draw_text(surface, text, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
            y += theme.FONT_SIZE_BODY + 2

    def _draw_loadout_detail(self, app, surface: pygame.Surface) -> None:
        for run_slot, button in self._slot_buttons.items():
            button.text = run_slot.upper()
            button.allow_skin = False
            button.text_align = "center"
            button.text_fit_mode = "ellipsis"
            button.max_font_role = "body"
            if self.active_slot == run_slot:
                button.bg = theme.COLOR_ACCENT_SOFT
                button.bg_hover = theme.COLOR_ACCENT
            else:
                button.bg = theme.COLOR_PANEL_ALT
                button.bg_hover = theme.COLOR_ACCENT_SOFT

        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        panel = self._summary_rect
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, panel, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, panel, width=2, border_radius=2)
        y = panel.top + 8
        chips = split_columns(pygame.Rect(panel.left + 8, y, panel.width - 16, 28), [1, 1, 1], gap=6)
        StatChip(chips[0], "Speed", f"{summary['speed_bonus']:+.2f}").draw(surface)
        StatChip(chips[1], "Carry", f"{summary['carry_bonus']:+.1f}").draw(surface)
        StatChip(chips[2], "InjuryRes", f"{summary['injury_resist']*100:.0f}%").draw(surface)
        y += 34
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        for line in wrap_text(f"Tags: {tags}", theme.get_font(theme.FONT_SIZE_META), panel.width - 16):
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED, (panel.left + 8, y))
            y += theme.FONT_SIZE_META + 2
        stats = [
            f"Stamina Mul {summary['stamina_mul']:.2f}",
            f"Hydration Mul {summary['hydration_mul']:.2f}",
        ]
        for line in stats:
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT, (panel.left + 8, y))
            y += theme.FONT_SIZE_META + 2
        y += 4
        draw_text(surface, "Equipped", theme.get_font(theme.FONT_SIZE_META, bold=True, kind="display"), theme.COLOR_TEXT, (panel.left + 8, y))
        y += theme.FONT_SIZE_META + 4
        for run_slot in RUN_SLOTS:
            current = getattr(app.current_loadout, run_slot)
            item_name = "-"
            if current and current in app.content.item_by_id:
                item_name = app.content.item_by_id[current].name
            elif current:
                item_name = current
            line = f"{run_slot}: {self._short_text(item_name, 24)}"
            if y + theme.get_font(theme.FONT_SIZE_META).get_linesize() > panel.bottom - 4:
                break
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED, (panel.left + 8, y))
            y += theme.FONT_SIZE_META + 2

    def _why_craft_now(self, app, recipe: Recipe) -> str:
        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        output_item = app.content.item_by_id.get(recipe.output_item)
        output_name = output_item.name if output_item else recipe.output_item
        category = (recipe.category or "").lower()
        if category == "pack" and float(summary["carry_bonus"]) < 8.0:
            return f"{output_name} raises carry capacity, so deeper pushes can return more loot."
        if category in {"armor", "utility"} and float(summary["injury_resist"]) < 0.10:
            return f"{output_name} improves survivability when hazard and combat events spike."
        if "water" in output_name.lower() or "filter" in output_name.lower():
            return f"{output_name} helps reduce hydration pressure, a common early run failure."
        return f"{output_name} improves option coverage and run consistency."

    def _draw_recipe_detail(self, app, surface: pygame.Surface) -> None:
        if not self.selected_recipe_id:
            EmptyState(self._detail_rect, "No Recipe", "Select a recipe from the list to review requirements and craft output.").draw(surface)
            return
        recipe = app.content.recipe_by_id.get(self.selected_recipe_id)
        if not recipe:
            EmptyState(self._detail_rect, "Missing Recipe", "Recipe data could not be resolved.").draw(surface)
            return
        unlocked = recipe.id in app.save_data.vault.blueprints
        output_item = app.content.item_by_id.get(recipe.output_item)
        y = self._detail_rect.top + 8
        bottom = self._detail_rect.bottom
        draw_text(surface, recipe.name, theme.get_font(theme.FONT_SIZE_TITLE, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
        y += 24
        if not unlocked:
            unlock_at = recipe.unlock_tav if recipe.unlock_tav is not None else 0
            draw_text(surface, f"LOCKED (Unlock at TAV {unlock_at})", theme.get_font(theme.FONT_SIZE_META, bold=True), theme.COLOR_WARNING, (self._detail_rect.left + 10, y))
            y += 20
            progress = max(0, int(app.save_data.vault.tav))
            target = max(1, int(unlock_at))
            pct = min(100, int((progress / target) * 100))
            draw_text(
                surface,
                f"Unlock Progress: {progress}/{target} TAV ({pct}%)",
                theme.get_font(theme.FONT_SIZE_META),
                theme.COLOR_TEXT_MUTED,
                (self._detail_rect.left + 10, y),
            )
            y += 18
        for line in wrap_text(recipe.description, theme.get_font(theme.FONT_SIZE_BODY), self._detail_rect.width - 20):
            if y + theme.get_font(theme.FONT_SIZE_BODY).get_linesize() > bottom:
                break
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
            y += theme.FONT_SIZE_BODY + 2
        if recipe.purpose:
            y += 6
            draw_text(surface, "Purpose", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
            y += 20
            purpose_lines, _ = clamp_wrapped_lines(recipe.purpose, theme.get_font(theme.FONT_SIZE_BODY), self._detail_rect.width - 20, max(0, bottom - y))
            for line in purpose_lines:
                draw_text(surface, line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
                y += theme.FONT_SIZE_BODY + 2
        y += 4
        draw_text(surface, "Why Craft This Now", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
        y += 20
        why_lines, _ = clamp_wrapped_lines(self._why_craft_now(app, recipe), theme.get_font(theme.FONT_SIZE_META), self._detail_rect.width - 20, max(0, bottom - y))
        for line in why_lines:
            draw_text(surface, line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
            y += theme.FONT_SIZE_META + 2
        y += 6
        craftable, reqs = can_craft(app.save_data.vault, recipe)
        draw_text(surface, "Requirements", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
        y += 20
        for item_id, (available, required) in reqs.items():
            color = theme.COLOR_SUCCESS if available >= required else theme.COLOR_WARNING
            if y + theme.get_font(theme.FONT_SIZE_BODY).get_linesize() > bottom:
                break
            draw_text(surface, f"{item_id.title()}: {available}/{required}", theme.get_font(theme.FONT_SIZE_BODY), color, (self._detail_rect.left + 10, y))
            y += theme.FONT_SIZE_BODY + 2
        y += 4
        output_name = output_item.name if output_item else recipe.output_item
        draw_text(surface, f"Output: {output_name} x{recipe.output_qty}", theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
        y += 18
        run_impact = []
        if output_item:
            mods = output_item.modifiers.model_dump(mode="python", exclude_none=True)
            if mods:
                run_impact = [f"{k}: {v:+.2f}" if isinstance(v, float) else f"{k}: {v}" for k, v in mods.items()]
        if run_impact:
            draw_text(surface, "Run Impact", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, (self._detail_rect.left + 10, y))
            y += 20
            impact_text = ", ".join(run_impact)
            impact_lines, _ = clamp_wrapped_lines(impact_text, theme.get_font(theme.FONT_SIZE_META), self._detail_rect.width - 20, max(0, bottom - y))
            for line in impact_lines:
                draw_text(surface, line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED, (self._detail_rect.left + 10, y))
                y += theme.FONT_SIZE_META + 2
        if output_item and output_item.tags:
            tag_text = ", ".join(output_item.tags)
            draw_text(surface, f"Unlocks Option Tags: {tag_text}", theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT, (self._detail_rect.left + 10, min(bottom - 18, y + 4)))
        hint = "Craft this in Crafting tab. Effects matter during run events."
        draw_text(
            surface,
            hint if (craftable and unlocked) else "Gather materials and unlock this recipe to craft.",
            theme.get_font(theme.FONT_SIZE_META),
            theme.COLOR_TEXT_MUTED,
            (self._detail_rect.left + 10, min(bottom - 2, y + 22)),
            "bottomleft",
        )

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        title = {
            "loadout": "Loadout",
            "equippable": "Gear Detail",
            "craftables": "Craftable Detail",
            "storage": "Storage Detail",
            "crafting": "Recipe Detail",
        }[self.tab]
        SectionCard(self._right_rect, title).draw(surface)
        if self.tab == "loadout":
            self._draw_loadout_detail(app, surface)
            return
        if self.tab == "crafting":
            self._draw_recipe_detail(app, surface)
            return
        self._draw_item_detail(app, surface)

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._panel_rect, title="Operations Command").draw(surface)

        mouse_pos = app.virtual_mouse_pos()
        for tab_key, button in self._tab_buttons.items():
            button.bg = theme.COLOR_ACCENT_SOFT if tab_key == self.tab else theme.COLOR_PANEL_ALT
            button.bg_hover = theme.COLOR_ACCENT
            button.draw(surface, mouse_pos)

        self._draw_left_panel(app, surface)
        self._draw_right_panel(app, surface)

        self._action_buttons["craft"].enabled = self.tab == "crafting"
        self._action_buttons["equip_selected"].enabled = self.tab == "loadout"
        self._action_buttons["equip_best"].enabled = self.tab == "loadout"
        self._action_buttons["equip_all"].enabled = self.tab == "loadout"

        for button in self.buttons:
            if button in self._tab_buttons.values() or button in self._action_buttons.values():
                continue
            button.draw(surface, mouse_pos)

        CommandStrip(self._footer_rect, list(self._action_buttons.values())).draw(surface, mouse_pos)

        if self.message:
            status_font = theme.get_font(theme.FONT_SIZE_BODY, bold=True)
            lines, _ = clamp_wrapped_lines(
                self.message,
                status_font,
                max(40, self._status_rect.width - 16),
                max(14, self._status_rect.height - 4),
                line_spacing=2,
            )
            if lines:
                draw_text(
                    surface,
                    lines[0],
                    status_font,
                    theme.COLOR_WARNING,
                    (self._status_rect.left + 8, self._status_rect.centery),
                    "midleft",
                )

        tip = hovered_tooltip(self.buttons)
        show_tips = True
        if app.save_data is not None:
            show_tips = bool(app.save_data.vault.settings.show_tooltips)
        if tip and show_tips:
            draw_tooltip_bar(surface, self._tooltip_rect, tip)

        if self.help_overlay:
            self._draw_help_overlay(surface)
        if self._vault_assistant and self._vault_assistant.visible:
            self._vault_assistant.draw(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 200, 720, 400)
        Panel(rect, title="Operations Help").draw(surface)
        lines = [
            "Loadout: click a slot, filter compatible gear, then Equip Selected.",
            "Equip Best respects active slot focus.",
            "Equippable: browse only gear that can be equipped.",
            "Craftables: browse crafted/consumable-focused items.",
            "Storage: full inventory plus separate materials strip.",
            "Crafting: recipes unlock over time via TAV milestones and drops.",
            "Press any key or click to close.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(theme.FONT_SIZE_SECTION), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(theme.FONT_SIZE_SECTION), theme.COLOR_TEXT, (rect.left + 14, y))
                y += theme.FONT_SIZE_SECTION + 4
            y += 2
