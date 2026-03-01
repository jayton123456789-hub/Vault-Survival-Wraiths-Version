from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from bit_life_survival.app.services.narrative import citizen_quip, event_flavor_line
from bit_life_survival.app.ui import theme
from bit_life_survival.app.ui.design_system import clamp_lines
from bit_life_survival.app.ui.overlays.tutorial import TutorialOverlay, TutorialStep
from bit_life_survival.app.ui.layout import split_columns, split_rows
from bit_life_survival.app.ui.widgets import (
    Button,
    CommandStrip,
    Panel,
    ProgressBar,
    SectionCard,
    StatChip,
    clamp_wrapped_lines,
    draw_text,
    draw_tooltip_bar,
    hovered_tooltip,
    wrap_text,
)
from bit_life_survival.core.drone import run_drone_recovery
from bit_life_survival.core.crafting import apply_milestone_blueprints, maybe_award_blueprint_drop
from bit_life_survival.core.engine import EventInstance, apply_choice_with_state_rng_detailed, create_initial_state, advance_to_next_event
from bit_life_survival.core.models import EquippedSlots, LogEntry, make_log_entry, sync_total_injury
from bit_life_survival.core.outcomes import OutcomeReport, apply_outcomes
from bit_life_survival.core.persistence import get_active_deploy_citizen, on_run_finished
from bit_life_survival.core.research import (
    contract_label,
    hunger_drain_multiplier,
    hydration_drain_multiplier,
    injury_relief_bonus,
    travel_speed_bonus,
)
from bit_life_survival.core.rng import DeterministicRNG
from bit_life_survival.core.run_director import (
    can_extract,
    next_extraction_target,
    reached_extraction_target,
    snapshot as director_snapshot,
    steps_until_next_wave,
)
from bit_life_survival.core.travel import compute_loadout_summary

from .core import Scene


RunFinish = Literal["death", "retreat", "extracted"]


def _clip_text_to_width(text: str, font: pygame.font.Font, width: int) -> str:
    if width <= 0:
        return ""
    if font.size(text)[0] <= width:
        return text
    ellipsis = "..."
    if font.size(ellipsis)[0] > width:
        return ""
    current = text
    while current and font.size(f"{current}{ellipsis}")[0] > width:
        current = current[:-1]
    return f"{current}{ellipsis}"


def _friendly_lock_hint(reasons: list[str]) -> str:
    if not reasons:
        return "Need compatible gear tags."
    raw = reasons[0].strip()
    cleaned = raw.replace("LOCKED:", "").strip()
    cleaned = cleaned.replace("Requires owned item with tag '", "Need gear with ")
    cleaned = cleaned.replace("Requires any item with tag '", "Need gear with ")
    cleaned = cleaned.replace("'.", " tag.")
    cleaned = cleaned.replace("'", "")
    if "Need gear with" not in cleaned and not cleaned.endswith("."):
        cleaned = f"{cleaned}."
    return cleaned


def _risk_badge(chance: float) -> tuple[str, tuple[int, int, int]]:
    if chance <= 0.01:
        return "Risk: Low", theme.COLOR_SUCCESS
    if chance <= 0.05:
        return "Risk: Med", theme.COLOR_WARNING
    return "Risk: High", theme.COLOR_DANGER


def _reward_badge(loot_bias: int) -> tuple[str, tuple[int, int, int]]:
    if loot_bias <= 0:
        return "Loot: Base", theme.COLOR_TEXT_MUTED
    if loot_bias == 1:
        return "Loot: +", theme.COLOR_ACCENT
    if loot_bias == 2:
        return "Loot: ++", theme.COLOR_ACCENT
    return "Loot: +++", theme.COLOR_ACCENT


def _option_preview_line(option) -> str:
    meters = {"stamina": 0.0, "hydration": 0.0, "morale": 0.0}
    injury_delta = 0.0
    for payload in list(option.costs) + list(option.outcomes):
        if "metersDelta" in payload:
            delta = payload["metersDelta"]
            for key in meters:
                meters[key] += float(delta.get(key, 0.0))
        if "addInjury" in payload:
            value = payload["addInjury"]
            if isinstance(value, dict):
                injury_delta += float(value.get("amount", 0.0))
            else:
                injury_delta += float(value)
    parts: list[str] = []
    for short, key in (("S", "stamina"), ("H", "hydration"), ("M", "morale")):
        delta = meters[key]
        if abs(delta) < 0.05:
            continue
        parts.append(f"{short}{delta:+.0f}")
    if abs(injury_delta) >= 0.1:
        parts.append(f"Inj{injury_delta:+.0f}")
    if not parts:
        return "No immediate meter shift."
    return " / ".join(parts)


def _recommended_actual_index(options: list[object]) -> int | None:
    unlocked: list[tuple[int, object]] = [(idx, option) for idx, option in enumerate(options) if not option.locked]
    if not unlocked:
        return None
    unlocked.sort(key=lambda pair: (float(pair[1].death_chance_hint), -int(pair[1].loot_bias), pair[0]))
    return unlocked[0][0]


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
        self.inventory_overlay = False
        self.inventory_tab = "consumables"
        self.finalized = False
        self._finish_kind: RunFinish = "death"
        self.tutorial_overlay: TutorialOverlay | None = None
        self.tutorial_pending = False
        self._defer_auto_step = False
        self._result_continue_rect = pygame.Rect(0, 0, 0, 0)
        self.deployed_citizen_id: str | None = None
        self.result_show_details = False

        self.buttons: list[Button] = []
        self._last_size: tuple[int, int] | None = None
        self.telemetry_rect = pygame.Rect(0, 0, 0, 0)
        self.loadout_rect = pygame.Rect(0, 0, 0, 0)
        self.injury_rect = pygame.Rect(0, 0, 0, 0)
        self._extract_button: Button | None = None
        self._event_option_rects: list[pygame.Rect] = []
        self._event_option_indices: list[int] = []
        self._inventory_item_rects: list[tuple[pygame.Rect, str]] = []

    def on_enter(self, app) -> None:
        self._app = app
        self.state = create_initial_state(self.run_seed, self.biome_id)
        self.state.mission_name = contract_label(app.save_data.vault)
        self.state.hunger_drain_mul = hunger_drain_multiplier(app.save_data.vault)
        self.state.hydration_drain_mul = hydration_drain_multiplier(app.save_data.vault)
        self.state.travel_speed_bonus = travel_speed_bonus(app.save_data.vault)
        self.state.medical_efficiency = injury_relief_bonus(app.save_data.vault)
        self.state.equipped = app.current_loadout.model_copy(deep=True)
        citizen = get_active_deploy_citizen(app.save_data.vault)
        app.save_data.vault.current_citizen = citizen
        self.deployed_citizen_id = citizen.id if citizen else None
        if citizen:
            for item_id, qty in citizen.kit.items():
                if qty > 0:
                    self.state.inventory[item_id] = self.state.inventory.get(item_id, 0) + int(qty)
            self._append_logs(
                app,
                [
                    make_log_entry(
                        self.state,
                        "system",
                        f"{citizen.name} enters the run with kit: "
                        + ", ".join(f"{item} x{qty}" for item, qty in sorted(citizen.kit.items())),
                    )
                ],
            )
        if not app.save_data.vault.settings.seen_run_help:
            self.help_overlay = True
            app.save_data.vault.settings.seen_run_help = True
            app.save_current_slot()
        if not bool(app.settings["gameplay"].get("tutorial_completed", False)) or bool(app.settings["gameplay"].get("replay_tutorial", False)):
            app.settings["gameplay"]["tutorial_completed"] = False
            app.settings["gameplay"]["replay_tutorial"] = False
            self.tutorial_pending = True
            self.tutorial_overlay = None
        if self.auto_step_once and self.tutorial_pending:
            self._defer_auto_step = True
        elif self.auto_step_once:
            self._continue_step(app)

    def _build_tutorial(self, app) -> None:
        if self.tutorial_overlay is not None:
            return
        self.tutorial_overlay = TutorialOverlay(
            [
                TutorialStep(
                    title="Travel, Then Decide",
                    body="Press Continue to advance one travel step and pause on the next event choice.",
                    target_rect_getter=lambda: self.bottom_rect,
                ),
                TutorialStep(
                    title="Survival Core",
                    body="Manage hunger and water before stamina bottoms out. Injury spikes still end runs fast.",
                    target_rect_getter=lambda: self.hud_rect,
                ),
                TutorialStep(
                    title="Push With A Purpose",
                    body="Deeper checkpoints return more scrap and TAV. Use Inventory for food, water, and aid before you commit.",
                    target_rect_getter=lambda: self.hud_rect,
                ),
            ],
            series_label="Run Guide",
            avoid_rect_getters=[
                lambda: self.bottom_rect,
                lambda: self.timeline_rect,
            ],
        )

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

    def _extract(self, app) -> None:
        if not self.state or self.event_overlay or self.result_overlay:
            return
        reached = reached_extraction_target(self.state.distance)
        if reached is None:
            target = next_extraction_target(self.state.distance)
            self.message = f"Extraction not ready. Reach {target:.1f} mi first."
            return
        if not can_extract(self.state.distance, self.state.step, self.state.seed):
            self.message = "Extraction channel is jammed during pressure wave."
            return
        self.state.dead = True
        self.state.death_reason = "Extracted successfully"
        self.state.death_flags.add("extracted")
        self._finish_kind = "extracted"
        self._append_logs(app, [make_log_entry(self.state, "system", f"Extraction successful at {self.state.distance:.2f} mi.")])

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
        category_map = {
            "travel": "TRAVEL",
            "event": "EVENT",
            "choice": "CHOICE",
            "outcome": "OUTCOME",
            "death": "INJURY",
            "system": "SYSTEM",
        }
        for entry in new_logs:
            app.gameplay_logger.info("[%s] %s", entry.type, entry.line)
            if self.state:
                self.state.append_run_log(
                    category=category_map.get(entry.type, "SYSTEM"),
                    message=entry.line,
                    details=entry.data or {},
                )

    def _continue_step(self, app) -> None:
        if not self.state or self.event_overlay or self.result_overlay:
            return
        _, event_instance, step_logs = advance_to_next_event(self.state, app.content)
        self._append_logs(app, step_logs)
        if self.state.dead:
            return
        if event_instance is not None:
            self.event_overlay = EventOverlay(event_instance=event_instance, travel_delta=self._extract_travel_delta(step_logs))
            self._event_option_rects = []
            self._event_option_indices = []

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
        self._event_option_rects = []
        self._event_option_indices = []

    def _select_event_option_from_display(self, display_index: int) -> None:
        if not self.event_overlay:
            return
        if not self._event_option_indices:
            self._select_event_option(display_index)
            return
        if display_index < 0 or display_index >= len(self._event_option_indices):
            self.message = "Option out of range."
            return
        self._select_event_option(self._event_option_indices[display_index])

    def _finalize_if_finished(self, app) -> None:
        if self.finalized or not self.state:
            return
        if not self.state.dead and self._finish_kind != "extracted":
            return
        self.finalized = True
        report = run_drone_recovery(app.save_data.vault, self.state, app.content)
        milestone_unlocks = apply_milestone_blueprints(app.save_data.vault)
        drop_unlock = maybe_award_blueprint_drop(
            app.save_data.vault,
            app.content.recipes,
            self.state.distance,
            self.state.rng_state,
            self.state.rng_calls,
        )
        blueprint_unlocks = list(milestone_unlocks)
        if drop_unlock and drop_unlock not in blueprint_unlocks:
            blueprint_unlocks.append(drop_unlock)
        report.blueprint_unlocks = blueprint_unlocks
        if blueprint_unlocks:
            pretty = ", ".join(blueprint_unlocks)
            self._append_logs(app, [make_log_entry(self.state, "system", f"Blueprint unlocks: {pretty}.")])
        app.save_data.vault.last_run_distance = float(self.state.distance)
        app.save_data.vault.last_run_time = int(self.state.time)
        on_run_finished(app.save_data.vault, result=self._finish_kind, citizen_id=self.deployed_citizen_id)
        app.save_data.vault.current_citizen = get_active_deploy_citizen(app.save_data.vault)
        app.current_loadout = EquippedSlots()
        app.save_current_slot()

        if self._finish_kind == "extracted":
            from .victory import VictoryScene

            app.change_scene(VictoryScene(final_state=self.state, recovery_report=report, logs=self.logs))
            return

        from .death import DeathScene

        app.change_scene(DeathScene(final_state=self.state, recovery_report=report, logs=self.logs, retreat=self._finish_kind == "retreat"))

    def _build_layout(self, app) -> None:
        if self._last_size == app.screen.get_size() and self.buttons:
            return
        self._last_size = app.screen.get_size()
        self._app = app
        self.buttons = []
        self._extract_button = None
        root = app.screen.get_rect().inflate(-16, -16)
        self.top_rect, mid_rect, self.bottom_rect = split_rows(root, [0.11, 0.73, 0.16], gap=10)
        self.timeline_rect, self.hud_rect = split_columns(mid_rect, [0.61, 0.39], gap=10)
        self.telemetry_rect, self.loadout_rect, self.injury_rect = split_rows(self.hud_rect, [0.44, 0.22, 0.34], gap=8)

        controls = split_columns(
            pygame.Rect(self.bottom_rect.left + 8, self.bottom_rect.top + 8, self.bottom_rect.width - 16, self.bottom_rect.height - 16),
            [2.0, 1, 1, 1, 1, 1, 1],
            gap=10,
        )
        self.buttons.append(
            Button(
                controls[0],
                "Continue Until Next Event",
                hotkey=pygame.K_c,
                on_click=lambda: self._continue_step(app),
                skin_key="continue",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Travel forward and trigger the next event.",
            )
        )
        self.buttons.append(
            Button(
                controls[1],
                "Show Log",
                hotkey=pygame.K_l,
                on_click=lambda: setattr(self, "show_full_log", not self.show_full_log),
                skin_key="show_log",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Toggle condensed/full timeline feed.",
            )
        )
        self.buttons.append(
            Button(
                controls[2],
                "Inventory",
                hotkey=pygame.K_i,
                on_click=lambda: setattr(self, "inventory_overlay", not self.inventory_overlay),
                skin_key="storage",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Open run inventory, gear, stats, and mission tracker.",
            )
        )
        self._extract_button = Button(
            controls[3],
            "Extract",
            hotkey=pygame.K_x,
            on_click=lambda: self._extract(app),
            skin_key="extract",
            skin_render_mode="frame_text",
            max_font_role="section",
            tooltip="End run safely once extraction target distance is reached.",
        )
        self.buttons.append(self._extract_button)
        self.buttons.append(
            Button(
                controls[4],
                "Quick Aid",
                hotkey=pygame.K_e,
                on_click=lambda: self._use_healing(app),
                skin_key="use_aid",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Use the first available medical item without opening inventory.",
            )
        )
        self.buttons.append(
            Button(
                controls[5],
                "Help",
                hotkey=pygame.K_h,
                on_click=lambda: setattr(self, "help_overlay", True),
                skin_key="help",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Show controls and run system guide.",
            )
        )
        self.buttons.append(
            Button(
                controls[6],
                "Quit",
                hotkey=pygame.K_q,
                on_click=lambda: self._quit_desktop(app),
                skin_key="quit",
                skin_render_mode="frame_text",
                max_font_role="section",
                tooltip="Quit to desktop after ending this run.",
            )
        )

    def _request_retreat(self, app) -> None:
        self.message = "Retreat is disabled in standard runs. Reach an extraction checkpoint or push on."

    def _quit_desktop(self, app) -> None:
        if not self.state:
            app.quit()
            return
        self.state.dead = True
        self.state.death_reason = "Run terminated"
        self._finish_kind = "death"
        self._append_logs(app, [make_log_entry(self.state, "system", "Run terminated. Drone dispatching for recovery.")])
        app.quit_after_scene = True

    def _use_healing(self, app, preferred_item_id: str | None = None) -> None:
        if not self.state or self.event_overlay or self.result_overlay:
            return
        candidates = (preferred_item_id,) if preferred_item_id else ("medkit_small", "med_armband", "antiseptic", "med_supplies")
        for item_id in candidates:
            if item_id is None:
                continue
            if int(self.state.inventory.get(item_id, 0)) <= 0:
                continue
            rng = DeterministicRNG(seed=self.state.seed, state=self.state.rng_state, calls=self.state.rng_calls)
            logs, report = apply_outcomes(
                self.state,
                [{"removeItems": [{"itemId": item_id, "qty": 1}]}],
                app.content,
                rng,
            )
            self.state.rng_state = rng.state
            self.state.rng_calls = rng.calls
            self._append_logs(app, logs)
            if abs(report.injury_effective_delta) > 1e-9 or report.notes:
                self.message = f"Used {item_id.replace('_', ' ')} to treat injuries."
            else:
                self.message = f"Used {item_id.replace('_', ' ')} but no treatment was needed."
            return
        self.message = "No healing item available in inventory."

    def _consume_inventory_item(self, item_id: str) -> None:
        if not self.state:
            return
        qty = int(self.state.inventory.get(item_id, 0))
        if qty <= 0:
            self.message = "Item not available."
            return
        if item_id in {"medkit_small", "med_armband", "antiseptic", "med_supplies"}:
            self._use_healing(self._app, preferred_item_id=item_id)
            return
        self.state.inventory[item_id] = qty - 1
        if self.state.inventory[item_id] <= 0:
            self.state.inventory.pop(item_id, None)
        if item_id == "water_pouch":
            self.state.meters.hydration = min(100.0, self.state.meters.hydration + 35.0)
            self.message = "Water used. Hydration stabilized."
        elif item_id == "ration_pack":
            self.state.hunger = min(100.0, self.state.hunger + 40.0)
            self.message = "Ration used. Hunger pressure eased."
        elif item_id == "energy_gel":
            self.state.meters.stamina = min(100.0, self.state.meters.stamina + 28.0)
            self.state.hunger = min(100.0, self.state.hunger + 8.0)
            self.message = "Energy gel used. Quick burst recovered."
        elif item_id == "signal_flare":
            self.state.meters.morale = min(100.0, self.state.meters.morale + 10.0)
            self.message = "Signal flare used. Morale rose."
        elif item_id == "repair_kit":
            torso = float(self.state.injuries.get("torso", 0.0))
            self.state.injuries["torso"] = max(0.0, torso - 5.0)
            sync_total_injury(self.state)
            self.message = "Repair kit repurposed into a quick patch."
        else:
            self.state.inventory[item_id] = self.state.inventory.get(item_id, 0) + 1
            self.message = "That item has no field use."
            return
        self._append_logs(
            self._app,
            [make_log_entry(self.state, "system", f"Used {item_id.replace('_', ' ')} from field inventory.")],
        )

    def _inventory_items(self) -> list[tuple[str, int]]:
        if not self.state:
            return []
        relevant_ids = (
            "water_pouch",
            "ration_pack",
            "energy_gel",
            "medkit_small",
            "med_armband",
            "med_supplies",
            "antiseptic",
            "signal_flare",
            "repair_kit",
        )
        return [(item_id, int(self.state.inventory.get(item_id, 0))) for item_id in relevant_ids if int(self.state.inventory.get(item_id, 0)) > 0]

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

        if self.inventory_overlay:
            if event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_i, pygame.K_ESCAPE}:
                    self.inventory_overlay = False
                    return
                if event.key == pygame.K_TAB:
                    order = ["consumables", "gear", "stats", "mission"]
                    next_idx = (order.index(self.inventory_tab) + 1) % len(order)
                    self.inventory_tab = order[next_idx]
                    return
                if event.key in {pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4}:
                    self.inventory_tab = ["consumables", "gear", "stats", "mission"][event.key - pygame.K_1]
                    return
                if self.inventory_tab == "consumables" and pygame.K_5 <= event.key <= pygame.K_9:
                    items = self._inventory_items()
                    idx = event.key - pygame.K_5
                    if idx < len(items):
                        self._consume_inventory_item(items[idx][0])
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, item_id in self._inventory_item_rects:
                    if rect.collidepoint(event.pos):
                        self._consume_inventory_item(item_id)
                        return
            return

        if self.result_overlay:
            if event.type == pygame.KEYDOWN:
                if event.key in {pygame.K_RETURN, pygame.K_SPACE}:
                    self.result_overlay = None
                    self._result_continue_rect = pygame.Rect(0, 0, 0, 0)
                    self.result_show_details = False
                elif event.key == pygame.K_TAB:
                    self.result_show_details = not self.result_show_details
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._result_continue_rect.collidepoint(event.pos):
                self.result_overlay = None
                self._result_continue_rect = pygame.Rect(0, 0, 0, 0)
                self.result_show_details = False
            return

        if self.event_overlay:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self._quit_desktop(app)
                    return
                if event.key == pygame.K_h:
                    self.help_overlay = True
                    return
                if event.key == pygame.K_i:
                    self.inventory_overlay = True
                    return
                if pygame.K_1 <= event.key <= pygame.K_9:
                    self._select_event_option_from_display(event.key - pygame.K_1)
                    return
                if event.key == pygame.K_RETURN:
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_event_modal_click(event.pos)
            return

        if self.tutorial_overlay and self.tutorial_overlay.visible:
            result = self.tutorial_overlay.handle_event(event)
            if result in {"done", "skip"}:
                self.tutorial_pending = False
                app.settings["gameplay"]["tutorial_completed"] = True
                app.save_settings()
                self.tutorial_overlay = None
            return

        for button in self.buttons:
            if button.handle_event(event):
                return

    def _handle_event_modal_click(self, pos: tuple[int, int]) -> None:
        if not self.event_overlay:
            return
        if self._event_option_rects:
            for idx, row in enumerate(self._event_option_rects):
                if row.collidepoint(pos):
                    self._select_event_option_from_display(idx)
                    return
            return
        modal_rect = self._event_modal_rect()
        options = self.event_overlay.event_instance.options
        start_y = modal_rect.top + 144
        for idx in range(len(options)):
            row = pygame.Rect(modal_rect.left + 18, start_y + idx * 56, modal_rect.width - 36, 50)
            if row.collidepoint(pos):
                self._select_event_option(idx)
                return

    def update(self, app, dt: float) -> None:
        if self.tutorial_pending and self.tutorial_overlay is None and not self.event_overlay and not self.result_overlay:
            self._build_tutorial(app)
        if self._defer_auto_step and not self.tutorial_pending and self.tutorial_overlay is None and not self.event_overlay:
            self._defer_auto_step = False
            self._continue_step(app)
        self._finalize_if_finished(app)
        if getattr(app, "quit_after_scene", False) and self.finalized:
            app.quit()

    def render(self, app, surface: pygame.Surface) -> None:
        self._build_layout(app)
        if self.tutorial_pending and not self.event_overlay and not self.result_overlay and self.tutorial_overlay is None:
            self._build_tutorial(app)
        app.backgrounds.draw(surface, self.state.biome_id if self.state else self.biome_id)

        if not self.state:
            draw_text(surface, "Initializing run...", theme.get_font(28), theme.COLOR_TEXT, surface.get_rect().center, "center")
            return
        if self._extract_button is not None:
            target = next_extraction_target(self.state.distance)
            reached = reached_extraction_target(self.state.distance)
            available = (
                reached is not None
                and can_extract(self.state.distance, self.state.step, self.state.seed)
                and not self.event_overlay
                and not self.result_overlay
            )
            self._extract_button.enabled = available
            if self._extract_button.enabled:
                self._extract_button.tooltip = f"Extract now from checkpoint {reached:.1f} mi."
            else:
                if reached is None:
                    self._extract_button.tooltip = f"Reach {target:.1f} mi before extracting."
                else:
                    self._extract_button.tooltip = "Pressure wave active. Wait for a clear step to extract."

        self._inventory_item_rects = []
        Panel(self.top_rect, title="Mission Strip").draw(surface)
        top_body = pygame.Rect(self.top_rect.left + 10, self.top_rect.top + 34, self.top_rect.width - 20, self.top_rect.height - 42)
        director = director_snapshot(self.state.distance, self.state.step, self.state.seed)
        top_chips = split_columns(
            pygame.Rect(top_body.left, top_body.top, top_body.width, min(30, top_body.height)),
            [1, 1, 1, 1, 1, 1, 1],
            gap=8,
        )
        wave_text = "Pulse" if director.wave_active else f"in {steps_until_next_wave(self.state.step)}"
        next_target = next_extraction_target(self.state.distance)
        reached = reached_extraction_target(self.state.distance)
        if reached is None:
            extract_text = f"{next_target:.0f} mi"
        elif can_extract(self.state.distance, self.state.step, self.state.seed):
            extract_text = f"Ready @ {reached:.0f}"
        else:
            extract_text = f"Jammed @ {reached:.0f}"
        StatChip(top_chips[0], "Distance", f"{self.state.distance:.2f} mi").draw(surface)
        StatChip(top_chips[1], "Time", str(self.state.time)).draw(surface)
        StatChip(top_chips[2], "Biome", self.state.biome_id).draw(surface)
        StatChip(top_chips[3], "Reward", f"x{director.reward_multiplier:.2f}").draw(surface)
        StatChip(top_chips[4], "Threat", f"T{director.threat_tier}").draw(surface)
        StatChip(top_chips[5], "Wave", wave_text).draw(surface)
        StatChip(top_chips[6], "Extract", extract_text).draw(surface)
        draw_text(
            surface,
            f"Mission: {self.state.mission_name}. Push deeper for more scrap and TAV, then extract clean.",
            theme.get_font(13),
            theme.COLOR_TEXT_MUTED,
            (top_body.left, top_body.bottom - 2),
            "bottomleft",
        )

        timeline_body = SectionCard(self.timeline_rect, "Timeline Feed").draw(surface)
        visible_count = 24 if self.show_full_log else 12
        y = timeline_body.top
        lines = [self._timeline_line(entry) for entry in self.logs[-visible_count:]]
        for line in lines:
            color = theme.COLOR_TEXT_MUTED
            if line.startswith("Result:"):
                color = theme.COLOR_TEXT
            elif line.startswith("Death:"):
                color = theme.COLOR_DANGER
            elif line.startswith("Event:"):
                color = theme.COLOR_ACCENT
            for wrapped in wrap_text(line, theme.get_font(15), timeline_body.width):
                draw_text(surface, wrapped, theme.get_font(15), color, (timeline_body.left, y))
                y += 18
            if y > timeline_body.bottom - 18:
                break

        telemetry_body = SectionCard(self.telemetry_rect, "Telemetry").draw(surface)
        meter_width = telemetry_body.width
        bars = [
            ("Stamina", self.state.meters.stamina, theme.COLOR_SUCCESS),
            ("Hydration", self.state.meters.hydration, theme.COLOR_ACCENT),
            ("Hunger", self.state.hunger, (208, 174, 104)),
            ("Morale", self.state.meters.morale, (180, 146, 255)),
            ("Injury", self.state.injury, theme.COLOR_DANGER),
        ]
        y = telemetry_body.top
        for label, value, color in bars:
            ProgressBar(pygame.Rect(telemetry_body.left, y, meter_width, 22), value=value, max_value=100.0, label=f"{label} {value:5.1f}", color=color).draw(surface)
            y += 30

        loadout_body = SectionCard(self.loadout_rect, "Loadout / Carry").draw(surface)
        carry_used, carry_cap = self._carry_stats()
        carry_line = f"{carry_used}/{carry_cap}" + (" OVER" if carry_used > carry_cap else "")
        chip_rects = split_columns(pygame.Rect(loadout_body.left, loadout_body.top, loadout_body.width, 28), [1, 1], gap=6)
        StatChip(chip_rects[0], "Carry", carry_line, tone=theme.COLOR_WARNING if carry_used > carry_cap else None).draw(surface)
        loadout = compute_loadout_summary(self.state, app.content)
        StatChip(chip_rects[1], "Speed", f"{loadout['speed_bonus']:+.2f}").draw(surface)
        tags = ", ".join(loadout["tags"]) if loadout["tags"] else "-"
        y = loadout_body.top + 34
        for line in wrap_text(f"Tags: {tags}", theme.get_font(14), loadout_body.width):
            draw_text(surface, line, theme.get_font(14), theme.COLOR_TEXT_MUTED, (loadout_body.left, y))
            y += 16

        injury_body = SectionCard(self.injury_rect, "Body Injury").draw(surface)
        y = injury_body.top
        for part in ("head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"):
            value = float(self.state.injuries.get(part, 0.0))
            if value >= 65:
                sev = "Severe"
                color = theme.COLOR_DANGER
            elif value >= 35:
                sev = "Moderate"
                color = theme.COLOR_WARNING
            elif value >= 12:
                sev = "Light"
                color = theme.COLOR_TEXT
            else:
                sev = "Clear"
                color = theme.COLOR_TEXT_MUTED
            label = part.replace("_", " ").title()
            draw_text(surface, f"{label}: {sev} ({value:.1f})", theme.get_font(13), color, (injury_body.left, y))
            y += 15
        if app.settings["gameplay"].get("show_advanced_overlay", False):
            y += 4
            draw_text(surface, f"RNG {self.state.rng_state}/{self.state.rng_calls}", theme.get_font(12), theme.COLOR_TEXT_MUTED, (injury_body.left, y))

        mouse_pos = app.virtual_mouse_pos()
        CommandStrip(self.bottom_rect, self.buttons).draw(surface, mouse_pos)

        tip = hovered_tooltip(self.buttons)
        if tip:
            tip_rect = pygame.Rect(self.bottom_rect.left + 8, self.bottom_rect.top - 30, self.bottom_rect.width - 16, 24)
            draw_tooltip_bar(surface, tip_rect, tip)

        if self.message:
            draw_text(surface, self.message, theme.get_font(18), theme.COLOR_WARNING, (self.bottom_rect.centerx, self.bottom_rect.top - 6), "midbottom")

        if self.event_overlay:
            self._draw_event_modal(surface)
        if self.result_overlay:
            self._draw_result_modal(surface)
        if self.help_overlay:
            self._draw_help_overlay(surface)
        if self.inventory_overlay:
            self._draw_inventory_overlay(surface)
        if self.tutorial_overlay and self.tutorial_overlay.visible and not self.event_overlay and not self.result_overlay:
            self.tutorial_overlay.draw(surface)

    def _event_modal_rect(self) -> pygame.Rect:
        return pygame.Rect(self._app.screen.get_width() // 2 - 420, self._app.screen.get_height() // 2 - 260, 840, 520)

    def _draw_event_modal(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))

        modal_rect = self._event_modal_rect()
        Panel(modal_rect, title="Event").draw(surface)
        event = self.event_overlay.event_instance
        draw_text(surface, event.title, theme.get_role_font("title", bold=True, kind="display"), theme.COLOR_TEXT, (modal_rect.left + 16, modal_rect.top + 42))
        y = modal_rect.top + 76
        flavor = event_flavor_line(self.state.seed, self.state.step, event.event_id, self.state.biome_id, event.tags)
        situation_lines: list[str] = []
        if flavor:
            situation_lines.extend(wrap_text(flavor, theme.get_role_font("meta"), modal_rect.width - 32))
        situation_lines.extend(wrap_text(event.text, theme.get_role_font("body"), modal_rect.width - 32))
        situation_lines = clamp_lines(situation_lines, 6)
        draw_text(surface, "Situation", theme.get_role_font("section", bold=True, kind="display"), theme.COLOR_TEXT, (modal_rect.left + 16, y))
        y += 22
        for line in situation_lines:
            draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (modal_rect.left + 16, y))
            y += theme.FONT_SIZE_META + 4
        y += 4
        quip = citizen_quip(self._app.save_data.vault.current_citizen.quirk if self._app.save_data.vault.current_citizen else None)
        if quip:
            for line in clamp_lines(wrap_text(quip, theme.get_role_font("meta"), modal_rect.width - 32), 2):
                draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_ACCENT, (modal_rect.left + 16, y))
                y += theme.FONT_SIZE_META + 3
            y += 4

        draw_text(surface, "Options", theme.get_role_font("section", bold=True, kind="display"), theme.COLOR_TEXT, (modal_rect.left + 16, y))
        y += 22
        self._event_option_rects = []
        self._event_option_indices = []
        core_options: list[tuple[int, object]] = []
        bonus_locked: list[tuple[int, object]] = []
        for actual_idx, option in enumerate(event.options):
            if option.locked:
                bonus_locked.append((actual_idx, option))
            else:
                core_options.append((actual_idx, option))
        ordered_options = core_options + bonus_locked
        recommended = _recommended_actual_index(event.options)

        draw_text(surface, "Core Path", theme.get_role_font("meta", bold=True), theme.COLOR_TEXT_MUTED, (modal_rect.left + 18, y))
        y += 18
        for display_idx, (actual_idx, option) in enumerate(ordered_options, start=1):
            if option.locked and bonus_locked and (actual_idx == bonus_locked[0][0]):
                y += 6
                draw_text(surface, "Bonus Locked Routes", theme.get_role_font("meta", bold=True), theme.COLOR_TEXT_MUTED, (modal_rect.left + 18, y))
                y += 18
            row = pygame.Rect(modal_rect.left + 18, y, modal_rect.width - 36, 50)
            self._event_option_rects.append(row.copy())
            self._event_option_indices.append(actual_idx)
            bg = theme.COLOR_PANEL_ALT if not option.locked else (66, 54, 54)
            pygame.draw.rect(surface, bg, row, border_radius=6)
            pygame.draw.rect(surface, theme.COLOR_BORDER, row, width=1, border_radius=6)
            label = f"[{display_idx}] {_clip_text_to_width(option.label, theme.get_font(16), row.width - 220)}"
            risk_text, risk_color = _risk_badge(float(option.death_chance_hint))
            reward_text, reward_color = _reward_badge(int(option.loot_bias))
            if option.locked:
                reason = _friendly_lock_hint(option.lock_reasons)
                label = f"[{display_idx}] Bonus Route (Locked)"
                hint = _clip_text_to_width(f"Optional bonus route: {reason}", theme.get_font(15), row.width - 20)
                draw_text(surface, hint, theme.get_font(15), theme.COLOR_TEXT_MUTED, (row.left + 8, row.bottom - 12), "midleft")
            else:
                preview = _clip_text_to_width(_option_preview_line(option), theme.get_font(14), row.width - 220)
                draw_text(surface, preview, theme.get_font(14), theme.COLOR_TEXT_MUTED, (row.left + 8, row.bottom - 12), "midleft")
            draw_text(surface, label, theme.get_font(16), theme.COLOR_TEXT if not option.locked else theme.COLOR_TEXT_MUTED, (row.left + 8, row.top + 16), "midleft")
            if recommended is not None and actual_idx == recommended:
                draw_text(surface, "RECOMMENDED", theme.get_font(12, bold=True), theme.COLOR_SUCCESS, (row.right - 108, row.top + 10), "midleft")
            draw_text(surface, reward_text, theme.get_font(14, bold=True), reward_color, (row.right - 108, row.centery - 8), "midleft")
            draw_text(surface, risk_text, theme.get_font(14, bold=True), risk_color, (row.right - 108, row.centery + 8), "midleft")
            y += 56
        hint = "Core options advance the contract. Bonus locked routes are optional. | 1-4 choose | I inventory | Q quit"
        draw_text(surface, hint, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (modal_rect.left + 16, modal_rect.bottom - 20), "midleft")

    def _draw_result_modal(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        modal_rect = pygame.Rect(self._app.screen.get_width() // 2 - 430, self._app.screen.get_height() // 2 - 280, 860, 560)
        Panel(modal_rect, title="Result").draw(surface)
        result = self.result_overlay
        y = modal_rect.top + 44
        draw_text(surface, f"{result.event_title} -> {result.option_label}", theme.get_role_font("section", bold=True, kind="display"), theme.COLOR_TEXT, (modal_rect.left + 16, y))
        y += 26
        for line in clamp_lines(wrap_text(result.option_log_line, theme.get_role_font("meta"), modal_rect.width - 32), 3):
            draw_text(surface, line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (modal_rect.left + 16, y))
            y += theme.FONT_SIZE_META + 4
        y += 6
        report = result.report
        injury_parts = ", ".join(
            f"{part.replace('_', ' ')} {delta:+.1f}"
            for part, delta in report.injury_part_delta.items()
            if abs(delta) > 1e-6
        ) or "-"
        lines = [
            (
                "Travel delta",
                f"S {result.travel_delta['stamina']:+.2f}, H {result.travel_delta['hydration']:+.2f}, M {result.travel_delta['morale']:+.2f}",
            ),
            (
                "Event delta",
                f"S {report.meters_delta['stamina']:+.2f}, H {report.meters_delta['hydration']:+.2f}, M {report.meters_delta['morale']:+.2f}",
            ),
            ("Injury", f"effective {report.injury_effective_delta:+.2f} (raw {report.injury_raw_delta:+.2f}) | {injury_parts}"),
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
        lines.append(("Notes", notes))

        visible_rows = lines if self.result_show_details else lines[:5]
        for key, value in visible_rows:
            if y > modal_rect.bottom - 90:
                break
            draw_text(surface, f"{key}:", theme.get_role_font("meta", bold=True), theme.COLOR_TEXT, (modal_rect.left + 16, y))
            if self.result_show_details:
                wrapped_values, _ = clamp_wrapped_lines(
                    value,
                    theme.get_role_font("meta"),
                    modal_rect.width - 220,
                    max(0, modal_rect.bottom - 92 - y),
                    line_spacing=4,
                )
            else:
                wrapped_values = clamp_lines(wrap_text(value, theme.get_role_font("meta"), modal_rect.width - 220), 2)
            for wrapped in wrapped_values:
                draw_text(surface, wrapped, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (modal_rect.left + 190, y))
                y += theme.FONT_SIZE_META + 4
            y += 2

        toggle_hint = "Tab for details" if not self.result_show_details else "Tab to collapse details"
        draw_text(surface, toggle_hint, theme.get_role_font("meta"), theme.COLOR_ACCENT, (modal_rect.left + 16, modal_rect.bottom - 52))
        self._result_continue_rect = pygame.Rect(modal_rect.centerx - 150, modal_rect.bottom - 36, 300, 24)
        pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, self._result_continue_rect, border_radius=2)
        pygame.draw.rect(surface, theme.COLOR_BORDER, self._result_continue_rect, width=1, border_radius=2)
        draw_text(
            surface,
            "Continue (Enter / Space / Click)",
            theme.get_role_font("meta"),
            theme.COLOR_TEXT_MUTED,
            self._result_continue_rect.center,
            "center",
        )

    def _draw_inventory_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 420, surface.get_height() // 2 - 280, 840, 560)
        Panel(rect, title="Field Inventory").draw(surface)
        tabs = ["consumables", "gear", "stats", "mission"]
        tab_rects = split_columns(pygame.Rect(rect.left + 16, rect.top + 44, rect.width - 32, 28), [1, 1, 1, 1], gap=6)
        for tab_rect, tab_id in zip(tab_rects, tabs):
            bg = theme.COLOR_ACCENT_SOFT if self.inventory_tab == tab_id else theme.COLOR_PANEL_ALT
            pygame.draw.rect(surface, bg, tab_rect, border_radius=4)
            pygame.draw.rect(surface, theme.COLOR_BORDER, tab_rect, width=1, border_radius=4)
            draw_text(surface, tab_id.title(), theme.get_role_font("meta", bold=True), theme.COLOR_TEXT, tab_rect.center, "center")

        body = pygame.Rect(rect.left + 16, rect.top + 84, rect.width - 32, rect.height - 112)
        self._inventory_item_rects = []
        if self.inventory_tab == "consumables":
            y = body.top
            items = self._inventory_items()
            if not items:
                draw_text(surface, "No usable field consumables right now.", theme.get_role_font("body"), theme.COLOR_TEXT_MUTED, (body.left, y))
            for idx, (item_id, qty) in enumerate(items[:5], start=1):
                item = self._app.content.item_by_id.get(item_id)
                row = pygame.Rect(body.left, y, body.width, 42)
                self._inventory_item_rects.append((row, item_id))
                pygame.draw.rect(surface, theme.COLOR_PANEL_ALT, row, border_radius=4)
                pygame.draw.rect(surface, theme.COLOR_BORDER, row, width=1, border_radius=4)
                draw_text(surface, f"[{idx + 4}] {(item.name if item else item_id)} x{qty}", theme.get_role_font("body"), theme.COLOR_TEXT, (row.left + 8, row.top + 12))
                help_line = {
                    "water_pouch": "Restores hydration.",
                    "ration_pack": "Restores hunger.",
                    "energy_gel": "Restores stamina with a small food boost.",
                    "signal_flare": "Raises morale.",
                }.get(item_id, "Medical and utility items apply their relevant field effect.")
                draw_text(surface, help_line, theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (row.left + 8, row.bottom - 10), "bottomleft")
                y += 48
        elif self.inventory_tab == "gear":
            y = body.top
            slots = self.state.equipped.model_dump(mode="python")
            for slot_name, item_id in slots.items():
                label = item_id
                if item_id and item_id in self._app.content.item_by_id:
                    label = self._app.content.item_by_id[item_id].name
                draw_text(surface, f"{slot_name}: {label or '-'}", theme.get_role_font("body"), theme.COLOR_TEXT if item_id else theme.COLOR_TEXT_MUTED, (body.left, y))
                y += theme.FONT_SIZE_BODY + 6
        elif self.inventory_tab == "stats":
            summary = compute_loadout_summary(self.state, self._app.content)
            lines = [
                f"Hydration: {self.state.meters.hydration:.1f}",
                f"Hunger: {self.state.hunger:.1f}",
                f"Injury: {self.state.injury:.1f}",
                f"Carry: {self._carry_stats()[0]}/{self._carry_stats()[1]}",
                f"Speed bonus: {summary['speed_bonus']:+.2f}",
                f"Carry bonus: {summary['carry_bonus']:+.1f}",
                f"Injury resist: {summary['injury_resist'] * 100:.0f}%",
                f"Hydration drain mod: x{summary['hydration_mul'] * self.state.hydration_drain_mul:.2f}",
                f"Hunger drain mod: x{self.state.hunger_drain_mul:.2f}",
            ]
            y = body.top
            for line in lines:
                draw_text(surface, line, theme.get_role_font("body"), theme.COLOR_TEXT, (body.left, y))
                y += theme.FONT_SIZE_BODY + 6
        else:
            target = next_extraction_target(self.state.distance)
            reached = reached_extraction_target(self.state.distance)
            progress = f"Checkpoint reached: {reached:.1f} mi" if reached is not None else f"Next checkpoint: {target:.1f} mi"
            lines = [
                f"Contract: {self.state.mission_name}",
                "Why go out: secure scrap, blueprints, and long-term TAV growth.",
                progress,
                "Why push farther: deeper checkpoints increase reward multipliers and salvage scrap.",
                "How to win: spend scrap in Research, unlock contracts, and complete the command tree.",
            ]
            y = body.top
            for line in lines:
                for wrapped in wrap_text(line, theme.get_role_font("body"), body.width):
                    draw_text(surface, wrapped, theme.get_role_font("body"), theme.COLOR_TEXT if line.startswith("Contract") else theme.COLOR_TEXT_MUTED, (body.left, y))
                    y += theme.FONT_SIZE_BODY + 4
                y += 2
        draw_text(surface, "1-4 tabs | I/Esc close | 5-9 use consumables", theme.get_role_font("meta"), theme.COLOR_TEXT_MUTED, (rect.left + 16, rect.bottom - 18), "midleft")

    def _draw_help_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(surface.get_width() // 2 - 360, surface.get_height() // 2 - 200, 720, 400)
        Panel(rect, title="Run Help").draw(surface)
        profile = director_snapshot(self.state.distance, self.state.step, self.state.seed)
        lines = [
            "Continue: move to the next event. There is no retreat in the normal run loop.",
            "Stay ahead of hunger, keep enough water, and patch injuries before stamina crashes.",
            "Use Inventory to spend food, water, medicine, and utility items in the field.",
            "Locked entries are bonus routes. Core routes always keep the run moving.",
            "Farther distance means higher scrap and TAV, but deeper drone recovery risk.",
            f"Run Profile: {profile.profile_name} ({profile.profile_blurb})",
            "Controls: C continue | L log | I inventory | X extract | E quick aid | H help | Q quit",
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
