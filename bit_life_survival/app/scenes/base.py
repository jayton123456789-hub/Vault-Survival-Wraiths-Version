from __future__ import annotations

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.claw_room import ClawRoom
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.overlays.tutorial import TutorialOverlay, TutorialStep
from bit_life_survival.app.ui.widgets import (
    Button,
    CommandStrip,
    Panel,
    SectionCard,
    StatChip,
    clamp_wrapped_lines,
    draw_text,
    draw_tooltip_bar,
    hovered_tooltip,
    wrap_text,
)
from bit_life_survival.core.models import GameState
from bit_life_survival.core.persistence import (
    citizen_queue_target,
    compute_roster_capacity,
    get_active_deploy_citizen,
    refill_citizen_queue,
    select_roster_citizen_for_deploy,
    storage_used,
    transfer_selected_citizen_to_roster,
)
from bit_life_survival.core.run_director import snapshot as director_snapshot
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene

MATERIAL_IDS = ("scrap", "cloth", "plastic", "metal")


class BaseScene(Scene):
    def __init__(self) -> None:
        self.message = ""
        self.buttons: list[Button] = []
        self.help_overlay = False
        self._last_size: tuple[int, int] | None = None
        self.active_context: str = "mission"
        self.expand_context: bool = False

        self.claw_room = ClawRoom()
        self._pending_claw_target_id: str | None = None
        self._context_buttons: dict[str, Button] = {}
        self._draft_button: Button | None = None
        self._claw_button: Button | None = None
        self._deploy_button: Button | None = None
        self._vault_assistant: TutorialOverlay | None = None
        self._assistant_stage: int | None = None
        self._assistant_mode: str | None = None

        self._top_rect = pygame.Rect(0, 0, 0, 0)
        self._stage_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_rect = pygame.Rect(0, 0, 0, 0)
        self._tav_chip_rect = pygame.Rect(0, 0, 0, 0)

        self._intake_room_rect = pygame.Rect(0, 0, 0, 0)
        self._deploy_room_rect = pygame.Rect(0, 0, 0, 0)
        self._selection_rect = pygame.Rect(0, 0, 0, 0)
        self._stage_actions_rect = pygame.Rect(0, 0, 0, 0)
        self._claw_controls_rect = pygame.Rect(0, 0, 0, 0)
        self._context_header_rect = pygame.Rect(0, 0, 0, 0)

        self._bottom_actions_rect = pygame.Rect(0, 0, 0, 0)
        self._context_buttons_rect = pygame.Rect(0, 0, 0, 0)
        self._context_panel_rect = pygame.Rect(0, 0, 0, 0)
        self._status_row_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_status_rect = pygame.Rect(0, 0, 0, 0)
        self._bottom_tooltip_rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def _assistant_session_flags(app) -> set[str]:
        flags = getattr(app, "_vault_assistant_seen", None)
        if not isinstance(flags, set):
            flags = set()
            setattr(app, "_vault_assistant_seen", flags)
        return flags

    def _assistant_config(self, app) -> tuple[bool, int, bool]:
        if not hasattr(app, "settings") or not isinstance(app.settings, dict):
            return False, 0, True
        gameplay = app.settings.setdefault("gameplay", {})
        enabled = bool(gameplay.get("vault_assistant_enabled", True))
        stage = int(gameplay.get("vault_assistant_stage", 0))
        completed = bool(gameplay.get("vault_assistant_completed", False))
        if bool(gameplay.get("replay_vault_assistant", False)):
            stage = 0
            completed = False
            gameplay["vault_assistant_stage"] = 0
            gameplay["vault_assistant_completed"] = False
            gameplay["vault_assistant_tav_briefed"] = False
            gameplay["replay_vault_assistant"] = False
            self._assistant_session_flags(app).clear()
            if hasattr(app, "save_settings"):
                app.save_settings()
        return enabled, stage, completed

    def _begin_post_run_assistant(self, app) -> None:
        if self._vault_assistant is not None:
            return
        if not hasattr(app, "settings") or not isinstance(app.settings, dict):
            return
        gameplay = app.settings.setdefault("gameplay", {})
        if not bool(gameplay.get("vault_assistant_enabled", True)):
            return
        if bool(gameplay.get("vault_assistant_tav_briefed", False)):
            return
        if "post_run_tav" in self._assistant_session_flags(app):
            return
        if app.save_data is None:
            return
        vault = app.save_data.vault
        if vault.run_counter < 1:
            return
        if float(vault.last_run_distance) <= 0.0 and int(vault.last_run_time) <= 0:
            return
        steps = [
            TutorialStep(
                title="Nice run - you gained TAV",
                body=(
                    "Tech Value (TAV) is your long-term progression currency. "
                    "Every finished run adds TAV, especially deeper runs."
                ),
                target_rect_getter=lambda: self._tav_chip_rect,
            ),
            TutorialStep(
                title="What TAV does",
                body=(
                    "Higher TAV unlocks new recipes, expands vault capacity, and compounds future runs. "
                    "Push farther, extract safely, and your next run gets stronger."
                ),
                target_rect_getter=lambda: self._bottom_actions_rect,
            ),
        ]
        self._assistant_mode = "post_run"
        self._vault_assistant = TutorialOverlay(
            steps,
            series_label="Vault Assistant",
            avoid_rect_getters=[
                lambda: self._bottom_actions_rect,
                lambda: self._claw_controls_rect,
            ],
        )

    def _begin_vault_assistant(self, app) -> None:
        if self._vault_assistant is not None:
            return
        enabled, stage, completed = self._assistant_config(app)
        if not enabled or completed:
            self._vault_assistant = None
            self._assistant_stage = None
            self._assistant_mode = None
            return
        if stage not in {0, 2}:
            self._vault_assistant = None
            self._assistant_stage = None
            self._assistant_mode = None
            return
        stage_key = f"stage_{stage}"
        if stage_key in self._assistant_session_flags(app):
            return
        if stage == 0:
            steps = [
                TutorialStep(
                    title="Intake Room",
                    body="Click an intake citizen first. This selects who the claw can grab.",
                    target_rect_getter=lambda: self._intake_room_rect,
                ),
                TutorialStep(
                    title="Claw Controls",
                    body="Use Draft Selected for instant transfer, or Use The Claw for animated transfer.",
                    target_rect_getter=lambda: self._claw_controls_rect,
                ),
                TutorialStep(
                    title="Command Row",
                    body="Operations is for gear/crafting. Deploy starts a run when an active runner is ready.",
                    target_rect_getter=lambda: self._bottom_actions_rect,
                ),
            ]
        else:
            steps = [
                TutorialStep(
                    title="Mission Context",
                    body="Intel card now combines mission objective, runner snapshot, and vault metrics.",
                    target_rect_getter=lambda: self._context_panel_rect,
                ),
                TutorialStep(
                    title="Runner Snapshot",
                    body="Runner snapshot in intel card is quick preview only. Full loadout edits stay in Operations.",
                    target_rect_getter=lambda: self._context_panel_rect,
                ),
                TutorialStep(
                    title="Run Loop",
                    body="Draft, gear up, deploy, recover, unlock blueprints, then push farther next run.",
                    target_rect_getter=lambda: self._bottom_actions_rect,
                ),
            ]
        self._assistant_stage = stage
        self._assistant_mode = "stage"
        label = "Vault Assistant (Run 1/3)" if stage == 0 else "Vault Assistant (Run 3/3)"
        self._vault_assistant = TutorialOverlay(
            steps,
            series_label=label,
            avoid_rect_getters=[
                lambda: self._bottom_actions_rect,
                lambda: self._claw_controls_rect,
            ],
        )

    def _finish_assistant_stage(self, app, skipped: bool = False) -> None:
        if self._assistant_mode is None:
            return
        if not hasattr(app, "settings") or not isinstance(app.settings, dict):
            self._assistant_stage = None
            self._vault_assistant = None
            self._assistant_mode = None
            return
        gameplay = app.settings.setdefault("gameplay", {})
        flags = self._assistant_session_flags(app)
        if self._assistant_mode == "post_run":
            gameplay["vault_assistant_tav_briefed"] = True
            flags.add("post_run_tav")
        else:
            if self._assistant_stage is None:
                return
            if skipped:
                gameplay["vault_assistant_completed"] = True
                gameplay["vault_assistant_stage"] = 3
            else:
                next_stage = min(3, int(self._assistant_stage) + 1)
                gameplay["vault_assistant_stage"] = next_stage
                gameplay["vault_assistant_completed"] = next_stage >= 3
            flags.add(f"stage_{int(self._assistant_stage)}")
        if hasattr(app, "save_settings"):
            app.save_settings()
        self._assistant_stage = None
        self._assistant_mode = None
        self._vault_assistant = None

    def on_enter(self, app) -> None:
        self._build_layout(app)
        self._begin_post_run_assistant(app)
        self._begin_vault_assistant(app)

    def _active_citizen(self, app):
        return get_active_deploy_citizen(app.save_data.vault)

    def _start_claw_transfer(self, app) -> None:
        if self.claw_room.is_animating:
            self.message = "Claw is already moving."
            return
        if len(app.save_data.vault.deploy_roster) >= app.save_data.vault.deploy_roster_capacity:
            self.message = "Deploy room is full."
            return
        target_id = self.claw_room.selected_intake_id
        if not target_id:
            self.message = "Select an intake citizen before using the claw."
            return
        if self.claw_room.start_grab(target_id):
            self._pending_claw_target_id = target_id
            self.message = "Claw engaged."

    def _finalize_claw_transfer(self, app, expected_id: str | None) -> None:
        if not expected_id:
            self.message = "Claw target missing."
            return
        try:
            citizen = transfer_selected_citizen_to_roster(app.save_data.vault, expected_id)
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
            self.message = "Select intake citizen first."
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

    def _open_operations(self, app, initial_tab: str = "loadout") -> None:
        from .operations import OperationsScene

        app.change_scene(OperationsScene(initial_tab=initial_tab))

    def _open_settings(self, app) -> None:
        from .settings import SettingsScene

        app.change_scene(SettingsScene(return_scene_factory=lambda: BaseScene()))

    def _open_menu(self, app) -> None:
        app.return_staged_loadout()
        from .menu import MainMenuScene

        app.change_scene(MainMenuScene())

    def _open_drone_bay(self, app) -> None:
        from .drone_bay import DroneBayScene

        app.change_scene(DroneBayScene())

    def _deploy(self, app) -> None:
        active = self._active_citizen(app)
        if active is None:
            self.message = "No deploy-ready citizen. Use the claw first."
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
            self.message = f"Selected {citizen.name}."
        else:
            self.message = "Intake citizen selected."

    def _story_status(self, app) -> tuple[str, list[str], str]:
        vault = app.save_data.vault
        queue_cap = citizen_queue_target(vault)
        roster_cap = compute_roster_capacity(vault)
        if vault.run_counter < 1:
            title = "Chapter 1: Seal and Scout"
            lines = [
                "Draft one citizen, equip gear, and launch your first run.",
                "Each run raises Tech Value and unlocks growth.",
            ]
            objective = "Finish your first run and recover any loot."
        elif vault.tav < 40:
            title = "Chapter 2: Stabilize the Grid"
            lines = [
                "Runs and recoveries raise Tech Value quickly.",
                "Higher TAV expands intake and deploy capacity.",
            ]
            objective = f"Reach TAV 40 (current {vault.tav})."
        else:
            title = "Chapter 3: Sustain the Vault"
            lines = [
                "Manage roster rotation and keep losses low.",
                "Drone upgrades improve bad-run recovery.",
            ]
            objective = "Maintain expedition tempo and upgrade steadily."
        cap_line = f"Intake {len(vault.citizen_queue)}/{queue_cap} | Deploy {len(vault.deploy_roster)}/{roster_cap}"
        return title, lines, f"{objective} {cap_line}"

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self.buttons = []
        self._context_buttons.clear()
        self._draft_button = None
        self._claw_button = None
        self._deploy_button = None

        root = app.screen.get_rect().inflate(-16, -16)
        self._top_rect, self._stage_rect, self._bottom_rect = split_rows(root, [0.12, 0.60, 0.28], gap=8)

        stage_inner = pygame.Rect(self._stage_rect.left + 10, self._stage_rect.top + 36, self._stage_rect.width - 20, self._stage_rect.height - 46)
        room_row, control_row = split_rows(stage_inner, [0.72, 0.28], gap=8)
        self._selection_rect, self._claw_controls_rect = split_rows(control_row, [0.52, 0.48], gap=8)
        self._stage_actions_rect = self._claw_controls_rect
        self._intake_room_rect, self._deploy_room_rect = split_columns(room_row, [1, 1], gap=10)

        stage_action_rows = split_columns(self._claw_controls_rect, [1, 1], gap=8)
        self._claw_button = Button(
            stage_action_rows[0],
            "Use The Claw",
            hotkey=pygame.K_u,
            on_click=lambda: self._start_claw_transfer(app),
            skin_key="use_the_claw",
            tooltip="Use claw on the selected intake citizen.",
            skin_render_mode="frame_text",
            max_font_role="section",
        )
        self._draft_button = Button(
            stage_action_rows[1],
            "Draft Selected",
            hotkey=pygame.K_RETURN,
            on_click=lambda: self._draft_selected_intake(app),
            skin_key="draft_selected",
            tooltip="Move selected intake citizen to deploy room.",
            skin_render_mode="frame_text",
            max_font_role="section",
        )
        self.buttons.append(self._claw_button)
        self.buttons.append(self._draft_button)

        bottom_inner = pygame.Rect(self._bottom_rect.left + 8, self._bottom_rect.top + 8, self._bottom_rect.width - 16, self._bottom_rect.height - 16)
        row_gap = 6
        available_h = max(0, bottom_inner.height - (row_gap * 2))
        action_h = max(44, int(available_h * 0.24))
        status_h = max(22, int(available_h * 0.14))
        context_h = max(112, available_h - action_h - status_h)

        y = bottom_inner.top
        self._bottom_actions_rect = pygame.Rect(bottom_inner.left, y, bottom_inner.width, action_h)
        y = self._bottom_actions_rect.bottom + row_gap
        self._context_buttons_rect = pygame.Rect(bottom_inner.left, y, bottom_inner.width, 0)
        self._context_panel_rect = pygame.Rect(bottom_inner.left, y, bottom_inner.width, max(0, context_h))
        y = self._context_panel_rect.bottom + row_gap
        self._status_row_rect = pygame.Rect(bottom_inner.left, y, bottom_inner.width, status_h)
        self._bottom_status_rect, self._bottom_tooltip_rect = split_columns(self._status_row_rect, [0.6, 0.4], gap=8)

        action_cols = split_columns(self._bottom_actions_rect, [1, 1, 1, 1, 1], gap=8)
        action_buttons = [
            Button(action_cols[0], "Operations", hotkey=pygame.K_l, on_click=lambda: self._open_operations(app, "loadout"), skin_key="loadout", tooltip="Open operations hub.", skin_render_mode="frame_text", max_font_role="section"),
            Button(action_cols[1], "Deploy", hotkey=pygame.K_d, on_click=lambda: self._deploy(app), skin_key="deploy", tooltip="Launch briefing and run.", skin_render_mode="frame_text", max_font_role="section"),
            Button(action_cols[2], "Drone Bay", hotkey=pygame.K_b, on_click=lambda: self._open_drone_bay(app), skin_key="drone_bay", tooltip="Open drone upgrades.", skin_render_mode="frame_text", max_font_role="section"),
            Button(action_cols[3], "Settings", hotkey=pygame.K_s, on_click=lambda: self._open_settings(app), skin_key="settings", tooltip="Video and gameplay settings.", skin_render_mode="frame_text", max_font_role="section"),
            Button(action_cols[4], "Main Menu", hotkey=pygame.K_ESCAPE, on_click=lambda: self._open_menu(app), skin_key="main_menu", tooltip="Return to main menu.", skin_render_mode="frame_text", max_font_role="section"),
        ]
        self._deploy_button = action_buttons[1]
        self.buttons.extend(action_buttons)

    def update(self, app, dt: float) -> None:
        if app.save_data is None:
            return
        refill_citizen_queue(app.save_data.vault)
        self.claw_room.sync(app.save_data.vault.citizen_queue, app.save_data.vault.deploy_roster)
        self.claw_room.update(dt)
        if self._vault_assistant is None:
            self._begin_post_run_assistant(app)
            self._begin_vault_assistant(app)
        finished_target = self.claw_room.consume_finished_target()
        if finished_target is not None:
            self._finalize_claw_transfer(app, expected_id=finished_target)

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
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            self.expand_context = not self.expand_context
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._context_header_rect.collidepoint(event.pos):
            self.expand_context = not self.expand_context
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._intake_room_rect.collidepoint(event.pos) or self._deploy_room_rect.collidepoint(event.pos):
                picked = self.claw_room.pick_actor(event.pos)
                if picked:
                    self._set_active_from_room_click(app, picked[0], picked[1])
                return

        for button in self.buttons:
            if button.handle_event(event):
                self._last_size = None
                return

    def _draw_top_bar(self, app, surface: pygame.Surface) -> None:
        vault = app.save_data.vault
        used = storage_used(vault)
        chips_rect = pygame.Rect(self._top_rect.left + 8, self._top_rect.top + 30, self._top_rect.width - 16, self._top_rect.height - 36)
        chips = split_columns(chips_rect, [1, 1, 1, 1], gap=8)
        self._tav_chip_rect = chips[1].copy()
        StatChip(chips[0], "Vault Lv", str(vault.vault_level)).draw(surface)
        StatChip(chips[1], "TAV", str(vault.tav)).draw(surface)
        StatChip(chips[2], "Drone Bay", str(int(vault.upgrades.get("drone_bay_level", 0)))).draw(surface)
        StatChip(chips[3], "Storage", str(used)).draw(surface)

    def _draw_selection_strip(self, app, surface: pygame.Surface) -> None:
        left, center, right = split_columns(self._selection_rect, [1, 1, 1], gap=8)
        intake_body = SectionCard(left, "Intake Selection").draw(surface)
        active_body = SectionCard(center, "Active Runner").draw(surface)
        deploy_body = SectionCard(right, "Deploy Selection").draw(surface)

        intake_sel = self.claw_room.selected_intake_id or "-"
        deploy_sel = self.claw_room.selected_roster_id or "-"
        active = self._active_citizen(app)

        draw_text(surface, intake_sel, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT, (intake_body.left, intake_body.top))
        draw_text(surface, active.name if active else "-", theme.get_font(theme.FONT_SIZE_BODY, bold=True), theme.COLOR_SUCCESS if active else theme.COLOR_TEXT_MUTED, (active_body.left, active_body.top))
        draw_text(surface, deploy_sel, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED, (deploy_body.left, deploy_body.top))

    def _draw_context_panel(self, app, surface: pygame.Surface) -> None:
        body = SectionCard(self._context_panel_rect, "Operations Intel").draw(surface)
        self._context_header_rect = pygame.Rect(self._context_panel_rect.left + 2, self._context_panel_rect.top + 2, self._context_panel_rect.width - 4, 22)
        x = body.left
        y = body.top
        bottom = body.bottom
        clipped = False

        def _draw_block(text: str, font: pygame.font.Font, color: tuple[int, int, int], spacing: int = 2) -> None:
            nonlocal y, clipped
            if y >= bottom:
                clipped = True
                return
            remaining = max(0, bottom - y)
            if self.expand_context:
                lines = wrap_text(text, font, body.width)
                was_clipped = False
            else:
                lines, was_clipped = clamp_wrapped_lines(text, font, body.width, remaining, line_spacing=spacing)
            for line in lines:
                if y + font.get_linesize() > bottom:
                    clipped = True
                    return
                draw_text(surface, line, font, color, (x, y))
                y += font.get_linesize() + spacing
            clipped = clipped or was_clipped

        chapter, lines, objective = self._story_status(app)
        next_seed = app.compute_run_seed() if hasattr(app, "compute_run_seed") else 0
        profile = director_snapshot(0.0, 0, next_seed)

        _draw_block(chapter, theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, spacing=3)
        for line in lines:
            _draw_block(line, theme.get_font(theme.FONT_SIZE_BODY), theme.COLOR_TEXT_MUTED)
        _draw_block(objective, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_WARNING)
        _draw_block(f"Next Run Profile: {profile.profile_name}", theme.get_font(theme.FONT_SIZE_META, bold=True), theme.COLOR_TEXT)
        _draw_block(profile.profile_blurb, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED)

        preview_state = GameState(
            seed=0,
            biome_id="suburbs",
            rng_state=1,
            rng_calls=0,
            equipped=app.current_loadout.model_copy(deep=True),
        )
        summary = compute_loadout_summary(preview_state, app.content)
        active = self._active_citizen(app)
        _draw_block("Runner Snapshot", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, spacing=3)
        _draw_block(
            f"Active: {active.name if active else '-'} | Speed {summary['speed_bonus']:+.2f} | Carry {summary['carry_bonus']:+.1f} | InjuryRes {summary['injury_resist']*100:.0f}%",
            theme.get_font(theme.FONT_SIZE_META),
            theme.COLOR_TEXT,
        )
        tags = ", ".join(summary["tags"]) if summary["tags"] else "-"
        _draw_block(f"Tags: {tags}", theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED)

        vault = app.save_data.vault
        queue_cap = citizen_queue_target(vault)
        roster_cap = compute_roster_capacity(vault)
        _draw_block("Vault Metrics", theme.get_font(theme.FONT_SIZE_SECTION, bold=True, kind="display"), theme.COLOR_TEXT, spacing=3)
        _draw_block(
            f"TAV {vault.tav} | Vault Lv {vault.vault_level} | Intake {len(vault.citizen_queue)}/{queue_cap} | Deploy {len(vault.deploy_roster)}/{roster_cap}",
            theme.get_font(theme.FONT_SIZE_META),
            theme.COLOR_TEXT,
        )
        material_line = " | ".join(f"{material_id.title()} {int(vault.materials.get(material_id, 0))}" for material_id in MATERIAL_IDS)
        _draw_block(material_line, theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED)

        locked_by_tav = [
            recipe
            for recipe in sorted(app.content.recipes, key=lambda r: (r.unlock_tav or 9999, r.name))
            if recipe.id not in vault.blueprints
        ]
        if locked_by_tav:
            next_recipe = locked_by_tav[0]
            unlock_at = next_recipe.unlock_tav if next_recipe.unlock_tav is not None else vault.tav
            delta = max(0, int(unlock_at) - int(vault.tav))
            _draw_block(f"Next unlock: {next_recipe.name}", theme.get_font(theme.FONT_SIZE_META, bold=True), theme.COLOR_TEXT)
            if delta > 0:
                _draw_block(f"TAV needed: +{delta}", theme.get_font(theme.FONT_SIZE_META), theme.COLOR_WARNING)
            else:
                _draw_block("Unlocked by blueprint drop", theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED)

        if clipped and not self.expand_context:
            hint_y = max(body.top, body.bottom - theme.get_font(theme.FONT_SIZE_META).get_linesize())
            draw_text(surface, "Tab: expand intel", theme.get_font(theme.FONT_SIZE_META), theme.COLOR_TEXT_MUTED, (x, hint_y))

    def render(self, app, surface: pygame.Surface) -> None:
        if app.save_data is None:
            from .menu import MainMenuScene

            app.change_scene(MainMenuScene("No save loaded."))
            return

        self._build_layout(app)
        app.backgrounds.draw(surface, "vault")
        Panel(self._top_rect, title="Vault Dashboard").draw(surface)
        Panel(self._stage_rect, title="Citizen Operations Deck").draw(surface)
        Panel(self._bottom_rect, title="Command Console").draw(surface)

        self._draw_top_bar(app, surface)
        self.claw_room.draw(
            surface,
            self._intake_room_rect,
            self._deploy_room_rect,
            app.save_data.vault.citizen_queue,
            app.save_data.vault.deploy_roster,
        )
        self._draw_selection_strip(app, surface)
        self._draw_context_panel(app, surface)

        if self._draft_button is not None:
            self._draft_button.enabled = (self.claw_room.selected_intake_id is not None) and (not self.claw_room.is_animating)
        if self._claw_button is not None:
            self._claw_button.enabled = (self.claw_room.selected_intake_id is not None) and (not self.claw_room.is_animating)
        if self._deploy_button is not None:
            deploy_ready = self._active_citizen(app) is not None
            self._deploy_button.enabled = deploy_ready
            self._deploy_button.tooltip = "Launch briefing and run." if deploy_ready else "Draft and select a deploy citizen first."

        mouse_pos = app.virtual_mouse_pos()
        CommandStrip(self._bottom_actions_rect, [btn for btn in self.buttons if btn.rect.colliderect(self._bottom_actions_rect)]).draw(surface, mouse_pos)
        for button in self.buttons:
            if button.rect.colliderect(self._bottom_actions_rect):
                continue
            button.draw(surface, mouse_pos)

        status_line = self.message
        if not status_line and self._deploy_button is not None and not self._deploy_button.enabled:
            status_line = "Draft and select a deploy citizen to enable Deploy."
        if status_line:
            status_font = theme.get_font(theme.FONT_SIZE_BODY, bold=True)
            status_lines, _ = clamp_wrapped_lines(
                status_line,
                status_font,
                max(40, self._bottom_status_rect.width - 16),
                max(14, self._bottom_status_rect.height - 4),
                line_spacing=2,
            )
            if status_lines:
                draw_text(
                    surface,
                    status_lines[0],
                    status_font,
                    theme.COLOR_WARNING,
                    (self._bottom_status_rect.left + 8, self._bottom_status_rect.centery),
                    "midleft",
                )

        tip = hovered_tooltip(self.buttons)
        if tip and app.save_data.vault.settings.show_tooltips:
            draw_tooltip_bar(surface, self._bottom_tooltip_rect, tip)

        if self.help_overlay:
            self._draw_help_overlay(surface)
        if self._vault_assistant and self._vault_assistant.visible:
            self._vault_assistant.draw(surface)

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 380, surface.get_height() // 2 - 220, 760, 440)
        Panel(rect, title="Base Help").draw(surface)
        lines = [
            "The center rooms are your intake/deploy workflow.",
            "Use The Claw now grabs the selected intake citizen.",
            "Bottom intel card now combines mission, runner snapshot, and vault metrics.",
            "Bottom command row controls operations and navigation.",
            "Click a deploy citizen to set the active runner.",
            "Press Tab or click context header to expand/collapse text.",
            "Press any key or click to close.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(theme.FONT_SIZE_SECTION), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(theme.FONT_SIZE_SECTION), theme.COLOR_TEXT, (rect.left + 14, y))
                y += theme.FONT_SIZE_SECTION + 4
            y += 2
