from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.claw_room import ClawRoom
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ScrollList, draw_text, draw_tooltip_bar, hovered_tooltip, wrap_text
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import (
    citizen_queue_target,
    compute_roster_capacity,
    get_active_deploy_citizen,
    refill_citizen_queue,
    select_roster_citizen_for_deploy,
    storage_used,
    transfer_claw_pick_to_roster,
    transfer_selected_citizen_to_roster,
)
from bit_life_survival.core.rng import DeterministicRNG
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


MATERIAL_IDS = ("scrap", "cloth", "plastic", "metal")


class BaseScene(Scene):
    def __init__(self) -> None:
        self.message = ""
        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.help_overlay = False

        self.claw_room = ClawRoom()
        self._pending_claw_target_id: str | None = None

        self.gear_preview_scroll: ScrollList | None = None
        self._gear_preview_items: list[str] = []

        self._top_rect = pygame.Rect(0, 0, 0, 0)
        self._left_rect = pygame.Rect(0, 0, 0, 0)
        self._center_rect = pygame.Rect(0, 0, 0, 0)
        self._right_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._intake_room_rect = pygame.Rect(0, 0, 0, 0)
        self._deploy_room_rect = pygame.Rect(0, 0, 0, 0)
        self._left_detail_rect = pygame.Rect(0, 0, 0, 0)
        self._materials_rect = pygame.Rect(0, 0, 0, 0)
        self._center_list_rect = pygame.Rect(0, 0, 0, 0)
        self._right_top_rect = pygame.Rect(0, 0, 0, 0)
        self._right_bottom_rect = pygame.Rect(0, 0, 0, 0)

    def _active_citizen(self, app):
        return get_active_deploy_citizen(app.save_data.vault)

    def _predict_claw_target_id(self, app) -> str | None:
        queue = app.save_data.vault.citizen_queue
        if not queue:
            return None
        vault = app.save_data.vault
        rng = DeterministicRNG(seed=vault.settings.base_seed, state=vault.claw_rng_state, calls=vault.claw_rng_calls)
        window = min(5, len(queue))
        idx = rng.next_int(0, max(1, window))
        return queue[idx].id

    def _start_claw_transfer(self, app) -> None:
        if self.claw_room.is_animating:
            self.message = "Claw is already moving."
            return
        if len(app.save_data.vault.deploy_roster) >= app.save_data.vault.deploy_roster_capacity:
            self.message = "Deploy room is full. Deploy or lose a citizen before drafting more."
            return
        target_id = self._predict_claw_target_id(app)
        if not target_id:
            self.message = "No citizens waiting in intake."
            return
        if self.claw_room.start_grab(target_id):
            self._pending_claw_target_id = target_id
            self.message = "Claw engaged: moving citizen to deploy room..."

    def _finalize_claw_transfer(self, app, expected_id: str | None) -> None:
        try:
            citizen = transfer_claw_pick_to_roster(app.save_data.vault, preview_count=5, expected_citizen_id=expected_id)
        except ValueError as exc:
            self.message = str(exc)
            return
        app.current_loadout = citizen.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.claw_room.selected_roster_id = citizen.id
        self._pending_claw_target_id = None
        self.message = f"{citizen.name} moved to deploy room."

    def _draft_selected_intake(self, app) -> None:
        if self.claw_room.is_animating:
            self.message = "Wait for claw animation to finish."
            return
        selected_id = self.claw_room.selected_intake_id
        if not selected_id:
            self.message = "Select a citizen in the intake room first."
            return
        try:
            citizen = transfer_selected_citizen_to_roster(app.save_data.vault, selected_id)
        except ValueError as exc:
            self.message = str(exc)
            return
        self.claw_room.selected_roster_id = citizen.id
        app.current_loadout = citizen.loadout.model_copy(deep=True)
        app.save_current_slot()
        self.message = f"Moved {citizen.name} to deploy room."

    def _open_storage(self, app) -> None:
        from .storage import StorageScene

        app.change_scene(StorageScene())

    def _open_loadout(self, app) -> None:
        active = self._active_citizen(app)
        if active is None:
            self.message = "Draft at least one citizen into deploy room first."
            return
        from .loadout import LoadoutScene

        app.current_loadout = active.loadout.model_copy(deep=True)
        app.save_data.vault.current_citizen = active
        app.change_scene(LoadoutScene())

    def _open_settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: BaseScene()))

    def _open_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _deploy(self, app) -> None:
        active = self._active_citizen(app)
        if active is None:
            self.message = "No deploy-ready citizen. Use The Claw first."
            return
        app.save_data.vault.current_citizen = active
        app.current_loadout = active.loadout.model_copy(deep=True)
        seed = app.compute_run_seed()
        app.save_data.vault.last_run_seed = seed
        app.save_data.vault.run_counter += 1
        app.save_current_slot()
        from .briefing import BriefingScene

        app.change_scene(BriefingScene(run_seed=seed))

    def _set_active_from_room_click(self, app, room: str, citizen_id: str) -> None:
        if room == "roster":
            try:
                citizen = select_roster_citizen_for_deploy(app.save_data.vault, citizen_id)
            except ValueError:
                self.message = "Could not select citizen."
                return
            app.current_loadout = citizen.loadout.model_copy(deep=True)
            app.save_current_slot()
            self.message = f"Selected {citizen.name} for next deploy."
        else:
            self.message = "Intake citizen selected. Move them with Draft Selected or Use The Claw."

    def _refresh_gear_preview(self, app) -> None:
        rows: list[str] = []
        for item_id, qty in sorted(app.save_data.vault.storage.items()):
            if qty <= 0:
                continue
            item = app.content.item_by_id.get(item_id)
            if not item:
                continue
            rows.append(f"{item.name}  x{qty}")
        self._gear_preview_items = rows
        if self.gear_preview_scroll:
            self.gear_preview_scroll.set_items(rows)

    def _story_status(self, app) -> tuple[str, list[str], str]:
        vault = app.save_data.vault
        queue_cap = citizen_queue_target(vault)
        roster_cap = compute_roster_capacity(vault)
        if vault.run_counter < 1:
            title = "Chapter 1: Seal and Scout"
            lines = [
                "You sealed the vault and activated the claw intake.",
                "Draft one citizen into Deploy Room, equip gear, and launch a first run.",
                "Every run raises Tech Value (TAV), which unlocks capacity and upgrades.",
            ]
            objective = "Objective: finish your first run and recover any loot."
        elif vault.tav < 40:
            title = "Chapter 2: Stabilize the Grid"
            lines = [
                "Power relays remain unstable.",
                "Salvage and successful recoveries increase Tech Value quickly.",
                "Higher Tech Value expands queue/roster capacity.",
            ]
            objective = f"Objective: reach Tech Value 40 (current {vault.tav})."
        else:
            title = "Chapter 3: Sustain the Vault"
            lines = [
                "Roster management now matters more than a single hero run.",
                "Rotate citizens, tune loadouts, and avoid unnecessary deaths.",
                "Drone Bay upgrades reduce losses on bad outcomes.",
            ]
            objective = "Objective: grow capacity and maintain stable expedition tempo."
        cap_line = f"Intake {len(vault.citizen_queue)}/{queue_cap} | Deploy Room {len(vault.deploy_roster)}/{roster_cap}"
        return title, lines, f"{objective}  {cap_line}"

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self.gear_preview_scroll = None

        root = app.screen.get_rect().inflate(-16, -16)
        top, body, bottom = split_rows(root, [0.15, 0.73, 0.12], gap=8)
        left, center, right = split_columns(body, [0.34, 0.36, 0.30], gap=8)
        self._top_rect, self._left_rect, self._center_rect, self._right_rect, self._bottom_rect = top, left, center, right, bottom

        left_inner = pygame.Rect(left.left + 10, left.top + 36, left.width - 20, left.height - 46)
        room_rows = split_rows(left_inner, [0.45, 0.31, 0.14, 0.10], gap=8)
        self._intake_room_rect, self._deploy_room_rect, self._left_detail_rect, action_row = room_rows
        action_cols = split_columns(action_row, [1, 1], gap=8)
        self.buttons.append(
            Button(
                action_cols[0],
                "Draft Selected",
                hotkey=pygame.K_RETURN,
                on_click=lambda: self._draft_selected_intake(app),
                tooltip="Move selected intake citizen into Deploy Room.",
            )
        )
        self.buttons.append(
            Button(
                action_cols[1],
                "Use The Claw",
                hotkey=pygame.K_u,
                on_click=lambda: self._start_claw_transfer(app),
                tooltip="Deterministic claw pick from intake queue to Deploy Room.",
            )
        )

        center_inner = pygame.Rect(center.left + 10, center.top + 36, center.width - 20, center.height - 46)
        module_row, material_row, hint_row, list_row = split_rows(center_inner, [0.12, 0.13, 0.08, 0.67], gap=8)
        self._materials_rect = material_row
        self._center_list_rect = list_row

        module_cols = split_columns(module_row, [1, 1, 1], gap=8)
        self.buttons.append(Button(module_cols[0], "Open Storage", on_click=lambda: self._open_storage(app), tooltip="Open dedicated storage scene."))
        self.buttons.append(Button(module_cols[1], "Crafting", on_click=lambda: setattr(self, "message", "Crafting panel coming next pass."), tooltip="Crafting module overview."))
        self.buttons.append(Button(module_cols[2], "Drone Bay", on_click=lambda: setattr(self, "message", "Drone Bay upgrades are managed from Settings/Progression."), tooltip="Drone recovery systems and upgrades."))
        self._center_hint_rect = hint_row

        self.gear_preview_scroll = ScrollList(list_row, row_height=30)
        self._refresh_gear_preview(app)

        right_inner = pygame.Rect(right.left + 10, right.top + 36, right.width - 20, right.height - 46)
        self._right_top_rect, self._right_bottom_rect = split_rows(right_inner, [0.56, 0.44], gap=8)

        bottom_cols = split_columns(pygame.Rect(bottom.left + 8, bottom.top + 8, bottom.width - 16, bottom.height - 16), [1, 1, 1, 1, 1], gap=8)
        self.buttons.extend(
            [
                Button(bottom_cols[0], "Loadout", hotkey=pygame.K_l, on_click=lambda: self._open_loadout(app), tooltip="Equip the active deploy citizen."),
                Button(bottom_cols[1], "Storage", hotkey=pygame.K_g, on_click=lambda: self._open_storage(app), tooltip="Open full storage view with filters."),
                Button(bottom_cols[2], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), tooltip="Open pre-deploy briefing and start run."),
                Button(bottom_cols[3], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), tooltip="Video/gameplay/audio settings."),
                Button(bottom_cols[4], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._open_menu(app), tooltip="Return to main menu."),
            ]
        )

    def update(self, app, dt: float) -> None:
        if app.save_data is None:
            return
        refill_citizen_queue(app.save_data.vault)
        self.claw_room.sync(app.save_data.vault.citizen_queue, app.save_data.vault.deploy_roster)
        self.claw_room.update(dt)
        finished_target = self.claw_room.consume_finished_target()
        if finished_target is not None:
            self._finalize_claw_transfer(app, expected_id=finished_target)

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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._intake_room_rect.collidepoint(event.pos) or self._deploy_room_rect.collidepoint(event.pos):
                picked = self.claw_room.pick_actor(event.pos)
                if picked:
                    self._set_active_from_room_click(app, picked[0], picked[1])
                return

        if self.gear_preview_scroll and self.gear_preview_scroll.handle_event(event):
            return
        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_top_bar(self, app, surface: pygame.Surface) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        line = (
            f"Vault Lv {vault.vault_level}    "
            f"Tech Value (TAV) {vault.tav}    "
            f"Drone Bay {int(vault.upgrades.get('drone_bay_level', 0))}    "
            f"Storage Used {used}"
        )
        draw_text(surface, line, theme.get_font(22, bold=True), theme.COLOR_TEXT, (self._top_rect.left + 14, self._top_rect.top + 52))

    def _draw_materials_row(self, app, surface: pygame.Surface) -> None:
        draw_text(surface, "Materials Pouch", theme.get_font(15, bold=True), theme.COLOR_TEXT_MUTED, (self._materials_rect.left + 2, self._materials_rect.top + 2))
        row = pygame.Rect(self._materials_rect.left, self._materials_rect.top + 20, self._materials_rect.width, self._materials_rect.height - 20)
        cols = split_columns(row, [1, 1, 1, 1], gap=8)
        for col, mid in zip(cols, MATERIAL_IDS):
            pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, col, border_radius=2)
            pygame.draw.rect(surface, theme.COLOR_BORDER, col, width=2, border_radius=2)
            draw_text(
                surface,
                f"{mid.title()} {app.save_data.vault.materials.get(mid, 0)}",
                theme.get_font(15, bold=True),
                theme.COLOR_TEXT,
                col.center,
                "center",
            )

    def _draw_left_detail(self, app, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._left_detail_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._left_detail_rect, width=2, border_radius=2)
        active = self._active_citizen(app)
        y = self._left_detail_rect.top + 8
        draw_text(surface, "Deploy Selection", theme.get_font(15, bold=True), theme.COLOR_TEXT, (self._left_detail_rect.left + 8, y))
        y += 18
        if active:
            draw_text(surface, f"{active.name}", theme.get_font(15, bold=True), theme.COLOR_SUCCESS, (self._left_detail_rect.left + 8, y))
            y += 16
            for line in wrap_text(active.quirk, theme.get_font(12), self._left_detail_rect.width - 16)[:2]:
                draw_text(surface, line, theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._left_detail_rect.left + 8, y))
                y += 14
        else:
            draw_text(surface, "No deploy citizen selected.", theme.get_font(12), theme.COLOR_WARNING, (self._left_detail_rect.left + 8, y))

    def _draw_center_panel(self, app, surface: pygame.Surface) -> None:
        self._draw_materials_row(app, surface)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._center_hint_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._center_hint_rect, width=1, border_radius=2)
        draw_text(
            surface,
            "Gear storage preview (full management in Storage screen).",
            theme.get_font(13),
            theme.COLOR_TEXT_MUTED,
            (self._center_hint_rect.left + 8, self._center_hint_rect.centery),
            "midleft",
        )
        if self.gear_preview_scroll:
            self.gear_preview_scroll.draw(surface)

    def _draw_right_panel(self, app, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._right_top_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._right_top_rect, width=2, border_radius=2)
        chapter, lines, objective = self._story_status(app)
        y = self._right_top_rect.top + 8
        draw_text(surface, chapter, theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._right_top_rect.left + 8, y))
        y += 24
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(13), self._right_top_rect.width - 16):
                draw_text(surface, wrapped, theme.get_font(13), theme.COLOR_TEXT_MUTED, (self._right_top_rect.left + 8, y))
                y += 16
            y += 2
        y += 4
        draw_text(surface, "What To Do Next", theme.get_font(18, bold=True), theme.COLOR_TEXT, (self._right_top_rect.left + 8, y))
        y += 22
        active = self._active_citizen(app)
        has_loadout = any(bool(v) for v in app.current_loadout.model_dump(mode="python").values())
        steps = [
            ("Move intake citizen into Deploy Room", bool(app.save_data.vault.deploy_roster)),
            ("Select a deploy citizen", active is not None),
            ("Open Loadout and equip gear", has_loadout),
            ("Press Deploy to start run", active is not None),
        ]
        for step_text, done in steps:
            prefix = "[OK]" if done else "[  ]"
            color = theme.COLOR_SUCCESS if done else theme.COLOR_TEXT
            draw_text(surface, f"{prefix} {step_text}", theme.get_font(14, bold=done), color, (self._right_top_rect.left + 8, y))
            y += 18
        draw_text(surface, objective, theme.get_font(12), theme.COLOR_WARNING, (self._right_top_rect.left + 8, self._right_top_rect.bottom - 14))

        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._right_bottom_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._right_bottom_rect, width=2, border_radius=2)
        draw_text(surface, "Loadout Preview", theme.get_font(17, bold=True), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, self._right_bottom_rect.top + 8))
        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        y = self._right_bottom_rect.top + 30
        for slot_name, item_id in app.current_loadout.model_dump(mode="python").items():
            draw_text(surface, f"{slot_name}: {item_id or '-'}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (self._right_bottom_rect.left + 8, y))
            y += 14
        y += 2
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        draw_text(surface, f"Tags: {tags}", theme.get_font(12), theme.COLOR_TEXT, (self._right_bottom_rect.left + 8, y))
        y += 14
        draw_text(
            surface,
            f"Speed {summary['speed_bonus']:+.2f}  Carry {summary['carry_bonus']:+.1f}",
            theme.get_font(12),
            theme.COLOR_TEXT_MUTED,
            (self._right_bottom_rect.left + 8, y),
        )

    def render(self, app, surface: pygame.Surface) -> None:
        if app.save_data is None:
            from .menu import MainMenuScene

            app.change_scene(MainMenuScene("No save loaded."))
            return

        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._left_rect, title="Citizen Operations").draw(surface)
        Panel(self._center_rect, title="Vault Modules").draw(surface)
        Panel(self._right_rect, title="Mission Context").draw(surface)
        Panel(self._bottom_rect).draw(surface)

        self._draw_top_bar(app, surface)
        self.claw_room.draw(
            surface,
            self._intake_room_rect,
            self._deploy_room_rect,
            app.save_data.vault.citizen_queue,
            app.save_data.vault.deploy_roster,
        )
        self._draw_left_detail(app, surface)
        self._draw_center_panel(app, surface)
        self._draw_right_panel(app, surface)

        mouse_pos = app.virtual_mouse_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top - 24, self._bottom_rect.width - 16, 18)
            draw_tooltip_bar(surface, tip_rect, tip)
        if self.message:
            draw_text(surface, self.message, theme.get_font(15), theme.COLOR_WARNING, (self._bottom_rect.centerx, self._bottom_rect.top - 4), "midbottom")
        if self.help_overlay:
            self._draw_help_overlay(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 380, surface.get_height() // 2 - 230, 760, 460)
        Panel(rect, title="Base Help").draw(surface)
        lines = [
            "Left room is intake queue. Right room is deploy roster.",
            "Use The Claw grabs one intake citizen and transports them to deploy room.",
            "Click a citizen in deploy room to select who will run next.",
            "Loadout edits the selected deploy citizen's equipment.",
            "Tech Value (TAV) is your long-term progression score from distance + recovery.",
            "Storage button always opens the full Storage scene.",
            "Press any key or click to close.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(17), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(17), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 22
            y += 3
