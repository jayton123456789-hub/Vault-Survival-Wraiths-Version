from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import Button, Panel, ProgressBar, draw_text, draw_tooltip_bar, hovered_tooltip, wrap_text
from bit_life_survival.core.drone import run_drone_recovery
from bit_life_survival.core.engine import EventInstance, apply_choice_with_state_rng_detailed, create_initial_state, advance_to_next_event
from bit_life_survival.core.models import EquippedSlots, LogEntry, make_log_entry
from bit_life_survival.core.outcomes import OutcomeReport
from bit_life_survival.core.persistence import refill_citizen_queue
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


RunFinish = Literal["death", "retreat"]


@dataclass(slots=True)
class EventOverlay:
    event_instance: EventInstance
    travel_delta: dict[str, float]


@dataclass(slots=True)
class ResultOverlay:
    event_title: str
    option_label: str
    option_log_line: str
    travel_delta: dict[str, float]
    report: OutcomeReport


class RunScene(Scene):
    def __init__(self, run_seed: int | str, biome_id: str = "suburbs", auto_step_once: bool = False) -> None:
        self.run_seed = run_seed
        self.biome_id = biome_id
        self.auto_step_once = auto_step_once
        self.state = None
        self.logs: list[LogEntry] = []
        self.show_full_log = False
        self.message = ""
        self.event_overlay: EventOverlay | None = None
        self.result_overlay: ResultOverlay | None = None
        self.help_overlay = False
        self.confirm_retreat_overlay = False
        self.finalized = False
        self._finish_kind: RunFinish = "death"

        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None

    def on_enter(self, app) -> None:
        self._app = app
        self.state = create_initial_state(self.run_seed, self.biome_id)
        self.state.equipped = app.current_loadout.model_copy(deep=True)
        if not app.save_data.vault.settings.seen_run_help:
            self.help_overlay = True
            app.save_data.vault.settings.seen_run_help = True
            app.save_current_slot()
        if self.auto_step_once:
            self._continue_step(app)

    def _carry_stats(self) -> tuple[int, int]:
        if not self.state:
            return 0, 1
        summary = compute_loadout_summary(self.state, self._app.content)
        capacity = 8 + max(0, int(round(summary["carry_bonus"])))
        used = sum(max(0, int(qty)) for qty in self.state.inventory.values())
        return used, max(1, capacity)

    def _apply_retreat(self, reason: str) -> None:
        if not self.state:
            return
        self.state.dead = True
        self.state.death_reason = reason
        self.state.death_flags.add("retreated_early")
        self._append_logs(self._app, [make_log_entry(self.state, "system", f"{reason} (recovery penalty applied).")])
        self._finish_kind = "retreat"

    def _extract_travel_delta(self, step_logs: list[LogEntry]) -> dict[str, float]:
        for entry in step_logs:
            data = entry.data or {}
            meters = data.get("metersDelta")
            if isinstance(meters, dict):
                return {
                    "stamina": float(meters.get("stamina", 0.0)),
                    "hydration": float(meters.get("hydration", 0.0)),
                    "morale": float(meters.get("morale", 0.0)),
                }
        return {"stamina": 0.0, "hydration": 0.0, "morale": 0.0}

    def _append_logs(self, app, new_logs: list[LogEntry]) -> None:
        if not new_logs:
            return
        self.logs.extend(new_logs)
        for entry in new_logs:
            app.gameplay_logger.info("[%s] %s", entry.type, entry.line)

    def _continue_step(self, app) -> None:
        if not self.state or self.event_overlay or self.result_overlay:
            return
        _, event_instance, step_logs = advance_to_next_event(self.state, app.content)
        self._append_logs(app, step_logs)
        if self.state.dead:
            return
        if event_instance is not None:
            self.event_overlay = EventOverlay(event_instance=event_instance, travel_delta=self._extract_travel_delta(step_logs))

    def _select_event_option(self, option_index: int) -> None:
        if not self.event_overlay or not self.state:
            return
        event_instance = self.event_overlay.event_instance
        if option_index < 0 or option_index >= len(event_instance.options):
            self.message = "Option out of range."
            return
        option = event_instance.options[option_index]
        if option.locked:
            self.message = "Option is locked."
            return
        resolution = apply_choice_with_state_rng_detailed(self.state, event_instance, option.id, self._app.content)
        self._append_logs(self._app, resolution.logs)
        self.result_overlay = ResultOverlay(
            event_title=event_instance.title,
            option_label=option.label,
            option_log_line=option.log_line,
            travel_delta=self.event_overlay.travel_delta,
            report=resolution.report,
        )
        self.event_overlay = None

    def _finalize_if_dead(self, app) -> None:
        if self.finalized or not self.state or not self.state.dead:
            return
        self.finalized = True
        report = run_drone_recovery(app.save_data.vault, self.state, app.content)
        app.save_data.vault.last_run_distance = float(self.state.distance)
        app.save_data.vault.last_run_time = int(self.state.time)
        app.save_data.vault.current_citizen = None
        refill_citizen_queue(app.save_data.vault, target_size=12)
        app.current_loadout = EquippedSlots()
        app.save_current_slot()

        from .death import DeathScene

        app.change_scene(DeathScene(final_state=self.state, recovery_report=report, logs=self.logs, retreat=self._finish_kind == "retreat"))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self._app = app
        self.buttons = []
        root = app.screen.get_rect().inflate(-20, -20)
        rows = split_rows(root, [0.10, 0.76, 0.14], gap=10)
        body_cols = split_columns(rows[1], [0.62, 0.38], gap=10)
        self.top_rect = rows[0]
        self.timeline_rect = body_cols[0]
        self.hud_rect = body_cols[1]
        self.bottom_rect = rows[2]

        controls = split_columns(
            pygame.Rect(self.bottom_rect.left + 8, self.bottom_rect.top + 10, self.bottom_rect.width - 16, self.bottom_rect.height - 20),
            [2.2, 1, 1, 1, 1],
            gap=10,
        )
        self.buttons.append(
            Button(
                controls[0],
                "Continue Until Next Event",
                hotkey=pygame.K_c,
                on_click=lambda: self._continue_step(app),
                tooltip="Travel forward and trigger the next event.",
            )
        )
        self.buttons.append(
            Button(
                controls[1],
                "Show Log",
                hotkey=pygame.K_l,
                on_click=lambda: setattr(self, "show_full_log", not self.show_full_log),
                tooltip="Toggle condensed/full timeline feed.",
            )
        )
        self.buttons.append(
            Button(
                controls[2],
                "Retreat",
                hotkey=pygame.K_r,
                on_click=lambda: self._request_retreat(app),
                tooltip="Return to vault early with a drone recovery penalty.",
            )
        )
        self.buttons.append(
            Button(
                controls[3],
                "Help",
                hotkey=pygame.K_h,
                on_click=lambda: setattr(self, "help_overlay", True),
                tooltip="Show controls and run system guide.",
            )
        )
        self.buttons.append(
            Button(
                controls[4],
                "Quit",
                hotkey=pygame.K_q,
                on_click=lambda: self._quit_desktop(app),
                tooltip="Quit to desktop after ending this run.",
            )
        )

    def _request_retreat(self, app) -> None:
        if bool(app.settings["gameplay"].get("confirm_retreat", True)):
            self.confirm_retreat_overlay = True
        else:
            self._apply_retreat("Retreated to base")

    def _quit_desktop(self, app) -> None:
        self._apply_retreat("Quit to desktop")
        app.quit_after_scene = True

    def handle_event(self, app, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            app.quit()
            return
        self._build_layout(app)
        if not self.state:
            return

        if self.help_overlay:
            if event.type in {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN}:
                self.help_overlay = False
            return

        if self.confirm_retreat_overlay:
            if event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_y, pygame.K_RETURN}:
                    self._apply_retreat("Retreated to base")
                    self.confirm_retreat_overlay = False
                elif event.key in {pygame.K_n, pygame.K_ESCAPE}:
                    self.confirm_retreat_overlay = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.confirm_retreat_overlay = False
            return

        if self.result_overlay:
            if event.type in {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN}:
                self.result_overlay = None
            return

        if self.event_overlay:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self._request_retreat(app)
                    return
                if event.key == pygame.K_q:
                    self._quit_desktop(app)
                    return
                if event.key == pygame.K_h:
                    self.help_overlay = True
                    return
                if pygame.K_1 <= event.key <= pygame.K_9:
                    self._select_event_option(event.key - pygame.K_1)
                    return
                if event.key == pygame.K_RETURN:
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_event_modal_click(event.pos)
            return

        for button in self.buttons:
            if button.handle_event(event):
                return

    def _handle_event_modal_click(self, pos: tuple[int, int]) -> None:
        if not self.event_overlay:
            return
        modal_rect = self._event_modal_rect()
        options = self.event_overlay.event_instance.options
        start_y = modal_rect.top + 120
        for idx in range(len(options)):
            row = pygame.Rect(modal_rect.left + 18, start_y + idx * 48, modal_rect.width - 36, 42)
            if row.collidepoint(pos):
                self._select_event_option(idx)
                return

    def update(self, app, dt: float) -> None:
        self._finalize_if_dead(app)
        if getattr(app, "quit_after_scene", False) and self.finalized:
            app.quit()

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        surface.fill(theme.COLOR_BG)

        if not self.state:
            draw_text(surface, "Initializing run...", theme.get_font(28), theme.COLOR_TEXT, surface.get_rect().center, "center")
            return

        Panel(self.top_rect, title="Run").draw(surface)
        Panel(self.timeline_rect, title="Timeline").draw(surface)
        Panel(self.hud_rect, title="Survival HUD").draw(surface)
        Panel(self.bottom_rect).draw(surface)

        draw_text(
            surface,
            f"Distance {self.state.distance:.2f}   Time {self.state.time}   Biome {self.state.biome_id}",
            theme.get_font(22, bold=True),
            theme.COLOR_TEXT,
            (self.top_rect.left + 14, self.top_rect.centery),
            "midleft",
        )

        # Timeline feed
        visible_count = 28 if self.show_full_log else 14
        lines = [self._timeline_line(entry) for entry in self.logs[-visible_count:]]
        y = self.timeline_rect.top + 40
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(15), self.timeline_rect.width - 24):
                draw_text(surface, wrapped, theme.get_font(15), theme.COLOR_TEXT_MUTED, (self.timeline_rect.left + 12, y))
                y += 18

        # HUD meters and carry
        meter_start = self.hud_rect.top + 40
        meter_width = self.hud_rect.width - 26
        bars = [
            ("Stamina", self.state.meters.stamina, theme.COLOR_SUCCESS),
            ("Hydration", self.state.meters.hydration, theme.COLOR_ACCENT),
            ("Morale", self.state.meters.morale, (180, 146, 255)),
            ("Injury", self.state.injury, theme.COLOR_DANGER),
        ]
        y = meter_start
        for label, value, color in bars:
            ProgressBar(pygame.Rect(self.hud_rect.left + 12, y, meter_width, 24), value=value, max_value=100.0, label=f"{label} {value:5.1f}", color=color).draw(surface)
            y += 34

        carry_used, carry_cap = self._carry_stats()
        carry_line = f"Carry: {carry_used}/{carry_cap}" + (" (OVER)" if carry_used > carry_cap else "")
        draw_text(surface, carry_line, theme.get_font(18, bold=True), theme.COLOR_WARNING if carry_used > carry_cap else theme.COLOR_TEXT, (self.hud_rect.left + 12, y + 4))
        y += 30

        loadout = compute_loadout_summary(self.state, app.content)
        tags = ", ".join(loadout["tags"]) if loadout["tags"] else "-"
        draw_text(surface, f"Tags: {tags}", theme.get_font(16), theme.COLOR_TEXT_MUTED, (self.hud_rect.left + 12, y))
        y += 24
        if app.settings["gameplay"].get("show_advanced_overlay", False):
            draw_text(surface, f"RNG state={self.state.rng_state} calls={self.state.rng_calls}", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self.hud_rect.left + 12, y))
            y += 18
            draw_text(surface, f"Cooldowns: {self.state.event_cooldowns}", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self.hud_rect.left + 12, y))
            y += 18
            draw_text(surface, f"Last Event: {self.state.last_event_id}", theme.get_font(14), theme.COLOR_TEXT_MUTED, (self.hud_rect.left + 12, y))

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(surface, mouse_pos)

        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self.bottom_rect.left + 8, self.bottom_rect.top - 34, self.bottom_rect.width - 16, 26)
            draw_tooltip_bar(surface, tip_rect, tip)

        if self.message:
            draw_text(surface, self.message, theme.get_font(18), theme.COLOR_WARNING, (self.bottom_rect.centerx, self.bottom_rect.top - 6), "midbottom")

        if self.event_overlay:
            self._draw_event_modal(surface)
        if self.result_overlay:
            self._draw_result_modal(surface)
        if self.help_overlay:
            self._draw_help_overlay(surface)
        if self.confirm_retreat_overlay:
            self._draw_confirm_retreat(surface)

    def _event_modal_rect(self) -> pygame.Rect:
        return pygame.Rect(self._app.screen.get_width() // 2 - 420, self._app.screen.get_height() // 2 - 260, 840, 520)

    def _draw_event_modal(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))

        modal_rect = self._event_modal_rect()
        Panel(modal_rect, title="Event").draw(surface)
        event = self.event_overlay.event_instance
        draw_text(surface, event.title, theme.get_font(28, bold=True), theme.COLOR_TEXT, (modal_rect.left + 16, modal_rect.top + 44))
        y = modal_rect.top + 82
        for line in wrap_text(event.text, theme.get_font(19), modal_rect.width - 32):
            draw_text(surface, line, theme.get_font(19), theme.COLOR_TEXT, (modal_rect.left + 16, y))
            y += 24
        y += 10
        for idx, option in enumerate(event.options, start=1):
            row = pygame.Rect(modal_rect.left + 18, y, modal_rect.width - 36, 42)
            bg = theme.COLOR_PANEL_ALT if not option.locked else (66, 54, 54)
            pygame.draw.rect(surface, bg, row, border_radius=6)
            pygame.draw.rect(surface, theme.COLOR_BORDER, row, width=1, border_radius=6)
            label = f"[{idx}] {option.label}"
            if option.locked:
                reason = "; ".join(option.lock_reasons) if option.lock_reasons else "Locked"
                label = f"{label} (LOCKED: {reason})"
            draw_text(surface, label, theme.get_font(16), theme.COLOR_TEXT if not option.locked else theme.COLOR_TEXT_MUTED, (row.left + 8, row.centery), "midleft")
            y += 48
        hint = "1-4 select option | R retreat | Q quit | H help | Enter dismiss"
        draw_text(surface, hint, theme.get_font(15), theme.COLOR_TEXT_MUTED, (modal_rect.left + 16, modal_rect.bottom - 20), "midleft")

    def _draw_result_modal(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        modal_rect = pygame.Rect(self._app.screen.get_width() // 2 - 430, self._app.screen.get_height() // 2 - 280, 860, 560)
        Panel(modal_rect, title="Result").draw(surface)
        result = self.result_overlay
        y = modal_rect.top + 44
        draw_text(surface, f"{result.event_title} -> {result.option_label}", theme.get_font(24, bold=True), theme.COLOR_TEXT, (modal_rect.left + 16, y))
        y += 34
        for line in wrap_text(result.option_log_line, theme.get_font(18), modal_rect.width - 32):
            draw_text(surface, line, theme.get_font(18), theme.COLOR_TEXT_MUTED, (modal_rect.left + 16, y))
            y += 22
        y += 8
        report = result.report
        lines = [
            (
                "Travel delta",
                f"S {result.travel_delta['stamina']:+.2f}, H {result.travel_delta['hydration']:+.2f}, M {result.travel_delta['morale']:+.2f}",
            ),
            (
                "Event delta",
                f"S {report.meters_delta['stamina']:+.2f}, H {report.meters_delta['hydration']:+.2f}, M {report.meters_delta['morale']:+.2f}",
            ),
            ("Injury", f"effective {report.injury_effective_delta:+.2f} (raw {report.injury_raw_delta:+.2f})"),
            ("Items gained", ", ".join(f"{k}x{v}" for k, v in sorted(report.items_gained.items())) or "-"),
            ("Items lost", ", ".join(f"{k}x{v}" for k, v in sorted(report.items_lost.items())) or "-"),
            ("Flags set", ", ".join(sorted(report.flags_set)) or "-"),
            ("Flags unset", ", ".join(sorted(report.flags_unset)) or "-"),
        ]
        if report.death_chance_rolls:
            rolls = "; ".join(
                f"{float(entry['chance'])*100:.1f}% / roll {float(entry['roll']):.4f} => {'DEATH' if bool(entry['triggered']) else 'safe'}"
                for entry in report.death_chance_rolls
            )
            lines.append(("Death chance", rolls))
        else:
            lines.append(("Death chance", "-"))
        notes = " ".join(report.notes) if report.notes else "-"
        lines.append(("Special notes", notes))

        for key, value in lines:
            draw_text(surface, f"{key}:", theme.get_font(16, bold=True), theme.COLOR_TEXT, (modal_rect.left + 16, y))
            for wrapped in wrap_text(value, theme.get_font(16), modal_rect.width - 220):
                draw_text(surface, wrapped, theme.get_font(16), theme.COLOR_TEXT_MUTED, (modal_rect.left + 190, y))
                y += 20
            y += 4
        draw_text(surface, "Press Enter or click to continue", theme.get_font(15), theme.COLOR_TEXT_MUTED, (modal_rect.centerx, modal_rect.bottom - 18), "center")

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 200, 720, 400)
        Panel(rect, title="Run Help").draw(surface)
        lines = [
            "Continue runs one travel step and then one event.",
            "Stamina/Hydration at 0 or high injury means run ends.",
            "Gear tags unlock event options.",
            "Death/retreat sends a drone to recover part of your gear.",
            "Controls: C continue, L log, R retreat, Q quit, H help.",
            "Event modal: number keys or click options.",
        ]
        y = rect.top + 54
        for line in lines:
            for wrapped in wrap_text(line, theme.get_font(18), rect.width - 28):
                draw_text(surface, wrapped, theme.get_font(18), theme.COLOR_TEXT, (rect.left + 14, y))
                y += 24
            y += 4
        draw_text(surface, "Press any key to close", theme.get_font(15), theme.COLOR_TEXT_MUTED, (rect.centerx, rect.bottom - 18), "center")

    def _draw_confirm_retreat(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 260, surface.get_height() // 2 - 100, 520, 200)
        Panel(rect, title="Confirm Retreat").draw(surface)
        draw_text(surface, "Retreat now? Recovery penalty will apply.", theme.get_font(20), theme.COLOR_TEXT, (rect.centerx, rect.centery - 10), "center")
        draw_text(surface, "Press Y to confirm, N to cancel.", theme.get_font(17), theme.COLOR_TEXT_MUTED, (rect.centerx, rect.centery + 26), "center")

    def _timeline_line(self, entry: LogEntry) -> str:
        prefix = {
            "travel": "Travel",
            "event": "Event",
            "choice": "Choice",
            "outcome": "Result",
            "death": "Death",
            "system": "System",
        }.get(entry.type, entry.type.title())
        return f"{prefix}: {entry.line}"
