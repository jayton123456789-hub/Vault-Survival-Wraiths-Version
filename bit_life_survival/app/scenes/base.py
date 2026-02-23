from __future__ import annotations

from dataclasses import dataclass

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, draw_text, wrap_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import draft_citizen_from_claw, refill_citizen_queue, store_item, take_item
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


@dataclass(slots=True)
class Recipe:
    id: str
    name: str
    inputs: dict[str, int]
    output_item: str
    output_qty: int = 1


RECIPES: list[Recipe] = [
    Recipe("field_pack", "Field Pack", {"scrap": 4, "cloth": 3, "plastic": 2}, "field_pack"),
    Recipe("patchwork_armor", "Patchwork Armor", {"scrap": 3, "metal": 4, "cloth": 2}, "patchwork_armor"),
    Recipe("filter_mask", "Filter Mask", {"plastic": 4, "cloth": 2, "metal": 1}, "filter_mask"),
    Recipe("lockpick_set", "Lockpick Set", {"metal": 3, "plastic": 1}, "lockpick_set"),
    Recipe("radio_parts", "Radio Parts", {"metal": 3, "plastic": 3}, "radio_parts"),
    Recipe("med_armband", "Medical Armband", {"cloth": 4, "plastic": 1}, "med_armband"),
]


class BaseScene(Scene):
    def __init__(self) -> None:
        self.message = ""
        self.selected_module = "storage"
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

    def _draw_top_bar(self, app, surface: pygame.Surface, rect: pygame.Rect) -> None:
        vault = app.save_data.vault
        storage_used = sum(max(0, qty) for qty in vault.storage.values())
        counts = {k: vault.storage.get(k, 0) for k in ("scrap", "cloth", "plastic", "metal")}
        line = (
            f"Vault Lv {vault.vault_level}   TAV {vault.tav}   Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}   "
            f"Storage Used {storage_used}   Scrap {counts['scrap']}   Cloth {counts['cloth']}   "
            f"Plastic {counts['plastic']}   Metal {counts['metal']}"
        )
        draw_text(surface, line, theme.get_font(20, bold=True), theme.COLOR_TEXT, (rect.left + 12, rect.centery), "midleft")

    def _craft(self, app, recipe: Recipe) -> None:
        vault = app.save_data.vault
        for item_id, qty in recipe.inputs.items():
            if vault.storage.get(item_id, 0) < qty:
                self.message = f"Missing materials for {recipe.name}."
                return
        for item_id, qty in recipe.inputs.items():
            take_item(vault, item_id, qty)
        store_item(vault, recipe.output_item, recipe.output_qty)
        app.save_current_slot()
        self.message = f"Crafted {recipe.output_qty}x {recipe.output_item}."

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
        from .run import RunScene

        app.change_scene(RunScene(run_seed=seed))

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
            )
        )

        module_row = pygame.Rect(self._center_rect.left + 12, self._center_rect.top + 40, self._center_rect.width - 24, 44)
        modules = split_columns(module_row, [1, 1, 1], gap=8)
        self.buttons.append(Button(modules[0], "Storage", on_click=lambda: setattr(self, "selected_module", "storage")))
        self.buttons.append(Button(modules[1], "Crafting", on_click=lambda: setattr(self, "selected_module", "crafting")))
        self.buttons.append(Button(modules[2], "Drone Bay", on_click=lambda: setattr(self, "selected_module", "drone")))

        bottom_cols = split_columns(pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top + 8, self._bottom_rect.width - 16, self._bottom_rect.height - 16), [1, 1, 1, 1], gap=10)
        self.buttons.append(Button(bottom_cols[0], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app)))
        self.buttons.append(Button(bottom_cols[1], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app)))
        self.buttons.append(Button(bottom_cols[2], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app)))
        self.buttons.append(Button(bottom_cols[3], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._main_menu(app)))

        if self.selected_module == "crafting":
            start_y = self._center_rect.top + 110
            for recipe in RECIPES:
                row = pygame.Rect(self._center_rect.left + 12, start_y, self._center_rect.width - 24, 34)
                self.buttons.append(Button(row, f"Craft: {recipe.name}", on_click=lambda r=recipe: self._craft(app, r)))
                start_y += 38

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
            self.message = "Controls: U claw, L loadout, D deploy, S settings, ESC menu."
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
        refill_citizen_queue(app.save_data.vault, target_size=12)
        self._build_layout(app)

        surface.fill(theme.COLOR_BG)
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._left_rect, title="Citizen Line").draw(surface)
        Panel(self._center_rect, title="Vault Modules").draw(surface)
        Panel(self._right_rect, title="Loadout Preview").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface, self._top_rect)
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            if self.selected_module == "crafting" and button.text.startswith("Craft:"):
                # Grey-out unavailable recipes.
                recipe_name = button.text.replace("Craft: ", "")
                recipe = next((r for r in RECIPES if r.name == recipe_name), None)
                if recipe:
                    button.enabled = all(app.save_data.vault.storage.get(item, 0) >= qty for item, qty in recipe.inputs.items())
            button.draw(surface, mouse_pos)

        queue = app.save_data.vault.citizen_queue[:5]
        y = self._left_rect.top + 48
        draw_text(surface, f"Queued Citizens: {len(app.save_data.vault.citizen_queue)}", theme.get_font(18), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 28
        for citizen in queue:
            draw_text(surface, f"- {citizen.name} ({citizen.quirk})", theme.get_font(16), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 14, y))
            y += 24
        current = app.save_data.vault.current_citizen
        y += 12
        draw_text(surface, "Current Draft:", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._left_rect.left + 12, y))
        y += 24
        if current:
            draw_text(surface, f"{current.name} - {current.quirk}", theme.get_font(16), theme.COLOR_SUCCESS, (self._left_rect.left + 12, y))
        else:
            draw_text(surface, "None", theme.get_font(16), theme.COLOR_TEXT_MUTED, (self._left_rect.left + 12, y))

        center_body = pygame.Rect(self._center_rect.left + 14, self._center_rect.top + 94, self._center_rect.width - 28, self._center_rect.height - 108)
        if self.selected_module == "storage":
            items = sorted((item_id, qty) for item_id, qty in app.save_data.vault.storage.items() if qty > 0)[:16]
            yy = center_body.top
            for item_id, qty in items:
                draw_text(surface, f"{item_id}: {qty}", theme.get_font(16), theme.COLOR_TEXT, (center_body.left, yy))
                yy += 22
        elif self.selected_module == "crafting":
            draw_text(surface, "Crafting recipes (greyed-out = missing materials):", theme.get_font(16), theme.COLOR_TEXT_MUTED, (center_body.left, center_body.top))
        else:
            level = int(app.save_data.vault.upgrades.get("drone_bay_level", 0))
            lines = [
                f"Drone Bay Level: {level}",
                "Higher levels improve recovery chance.",
                "Upgrade paths arrive in later phases.",
            ]
            yy = center_body.top
            for line in lines:
                draw_text(surface, line, theme.get_font(16), theme.COLOR_TEXT, (center_body.left, yy))
                yy += 24

        # Right preview: tags + modifiers from staged loadout.
        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        yy = self._right_rect.top + 50
        draw_text(surface, "Equipped:", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_rect.left + 12, yy))
        yy += 24
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

        if self.message:
            draw_text(surface, self.message, theme.get_font(17), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 8), "midbottom")
