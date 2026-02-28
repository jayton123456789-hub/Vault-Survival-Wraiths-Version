from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .loader import ContentBundle
from .models import GameState, LogEntry, make_log_entry
from .outcomes import OutcomeReport, apply_outcomes
from .requirements import evaluate_requirement
from .rng import DeterministicRNG
from .selector import select_event
from .travel import advance_travel

AutopickPolicy = Literal["safe", "random", "greedy"]
DEFAULT_EVENT_COOLDOWN_STEPS = 1


@dataclass(slots=True)
class EventOptionInstance:
    id: str
    label: str
    locked: bool
    lock_reasons: list[str]
    requirements: dict[str, Any] | None
    costs: list[dict[str, Any]]
    outcomes: list[dict[str, Any]]
    log_line: str
    death_chance_hint: float
    loot_bias: int


@dataclass(slots=True)
class EventInstance:
    event_id: str
    title: str
    text: str
    tags: list[str]
    options: list[EventOptionInstance]


@dataclass(slots=True)
class ChoiceResolution:
    logs: list[LogEntry]
    report: OutcomeReport


def _rng_from_state(state: GameState) -> DeterministicRNG:
    return DeterministicRNG(seed=state.seed, state=state.rng_state, calls=state.rng_calls)


def _sync_rng_to_state(state: GameState, rng: DeterministicRNG) -> None:
    state.rng_state = rng.state
    state.rng_calls = rng.calls


def create_initial_state(seed: int | str, biome_id: str) -> GameState:
    rng = DeterministicRNG.from_seed(seed)
    return GameState(seed=seed, biome_id=biome_id, rng_state=rng.state, rng_calls=rng.calls)


def _decrement_cooldowns(state: GameState) -> None:
    next_cooldowns: dict[str, int] = {}
    for event_id, remaining in state.event_cooldowns.items():
        next_remaining = remaining - 1
        if next_remaining > 0:
            next_cooldowns[event_id] = next_remaining
    state.event_cooldowns = next_cooldowns


def _option_death_chance(option_payload: list[dict[str, Any]]) -> float:
    chance = 0.0
    for outcome in option_payload:
        if "setDeathChance" in outcome:
            chance = max(chance, float(outcome["setDeathChance"]))
    return chance


def _option_loot_bias(option_payload: list[dict[str, Any]]) -> int:
    bias = 0
    for outcome in option_payload:
        if "lootRoll" in outcome:
            bias += int(outcome["lootRoll"].get("rolls", 1))
        if "addItems" in outcome:
            bias += len(outcome["addItems"])
    return bias


def _instantiate_event(event: Any, state: GameState, content: ContentBundle) -> EventInstance:
    options: list[EventOptionInstance] = []
    for option in event.options:
        death_hint = max(_option_death_chance(option.costs), _option_death_chance(option.outcomes))
        loot_bias = _option_loot_bias(option.outcomes)
        if option.requirements is None:
            options.append(
                EventOptionInstance(
                    id=option.id,
                    label=option.label,
                    locked=False,
                    lock_reasons=[],
                    requirements=option.requirements,
                    costs=option.costs,
                    outcomes=option.outcomes,
                    log_line=option.log_line,
                    death_chance_hint=death_hint,
                    loot_bias=loot_bias,
                )
            )
            continue

        ok, reasons = evaluate_requirement(option.requirements, state, content)
        options.append(
            EventOptionInstance(
                id=option.id,
                label=option.label,
                locked=not ok,
                lock_reasons=reasons,
                requirements=option.requirements,
                costs=option.costs,
                outcomes=option.outcomes,
                log_line=option.log_line,
                death_chance_hint=death_hint,
                loot_bias=loot_bias,
            )
        )
    return EventInstance(event_id=event.id, title=event.title, text=event.text, tags=event.tags, options=options)


def _choose_option(
    policy: AutopickPolicy,
    event_instance: EventInstance,
    rng: DeterministicRNG,
) -> EventOptionInstance | None:
    unlocked = [option for option in event_instance.options if not option.locked]
    if not unlocked:
        return None

    if policy == "random":
        return unlocked[rng.next_int(0, len(unlocked))]

    if policy == "safe":
        if any(option.death_chance_hint > 0 for option in unlocked):
            ordered = sorted(
                enumerate(unlocked),
                key=lambda pair: (pair[1].death_chance_hint, pair[0]),
            )
            return ordered[0][1]
        return unlocked[0]

    # greedy
    ordered = sorted(
        enumerate(unlocked),
        key=lambda pair: (pair[1].loot_bias, -pair[1].death_chance_hint, -pair[0]),
        reverse=True,
    )
    return ordered[0][1]


def apply_choice_detailed(
    state: GameState,
    event_instance: EventInstance,
    option_id: str,
    content: ContentBundle,
    rng: DeterministicRNG,
) -> ChoiceResolution:
    option = next((option for option in event_instance.options if option.id == option_id), None)
    if option is None:
        raise ValueError(f"Option '{option_id}' not found on event '{event_instance.event_id}'.")
    if option.locked:
        return ChoiceResolution(
            logs=[
                make_log_entry(
                    state,
                    "system",
                    f"Choice '{option.label}' is locked: {'; '.join(option.lock_reasons) or 'unknown reason'}",
                )
            ],
            report=OutcomeReport(),
        )

    logs: list[LogEntry] = [
        make_log_entry(
            state,
            "choice",
            option.log_line,
            data={"eventId": event_instance.event_id, "optionId": option.id},
        )
    ]
    report = OutcomeReport()
    if option.costs:
        cost_logs, cost_report = apply_outcomes(state, option.costs, content, rng)
        logs.extend(cost_logs)
        report.merge(cost_report)
    if not state.dead:
        outcome_logs, outcome_report = apply_outcomes(state, option.outcomes, content, rng)
        logs.extend(outcome_logs)
        report.merge(outcome_report)
    return ChoiceResolution(logs=logs, report=report)


def apply_choice(
    state: GameState,
    event_instance: EventInstance,
    option_id: str,
    content: ContentBundle,
    rng: DeterministicRNG,
) -> list[LogEntry]:
    return apply_choice_detailed(state, event_instance, option_id, content, rng).logs


def apply_choice_with_state_rng(
    state: GameState,
    event_instance: EventInstance,
    option_id: str,
    content: ContentBundle,
) -> list[LogEntry]:
    rng = _rng_from_state(state)
    logs = apply_choice(state, event_instance, option_id, content, rng)
    _sync_rng_to_state(state, rng)
    return logs


def apply_choice_with_state_rng_detailed(
    state: GameState,
    event_instance: EventInstance,
    option_id: str,
    content: ContentBundle,
) -> ChoiceResolution:
    rng = _rng_from_state(state)
    resolution = apply_choice_detailed(state, event_instance, option_id, content, rng)
    _sync_rng_to_state(state, rng)
    return resolution


def advance_to_next_event(
    state: GameState,
    content: ContentBundle,
) -> tuple[GameState, EventInstance | None, list[LogEntry]]:
    rng = _rng_from_state(state)
    logs: list[LogEntry] = []
    _decrement_cooldowns(state)

    logs.extend(advance_travel(state, content))
    if state.dead:
        _sync_rng_to_state(state, rng)
        return state, None, logs

    event = select_event(state, content, rng)
    if event is None:
        logs.append(make_log_entry(state, "system", "No event triggered this step."))
        _sync_rng_to_state(state, rng)
        return state, None, logs

    cooldown_steps = event.trigger.cooldown_steps
    if cooldown_steps is None:
        cooldown_steps = DEFAULT_EVENT_COOLDOWN_STEPS
    if cooldown_steps > 0:
        state.event_cooldowns[event.id] = cooldown_steps

    state.last_event_id = event.id
    state.recent_event_ids.append(event.id)
    if len(state.recent_event_ids) > 7:
        state.recent_event_ids = state.recent_event_ids[-7:]

    event_instance = _instantiate_event(event, state, content)
    logs.append(make_log_entry(state, "event", f"{event.title}: {event.text}", data={"eventId": event.id}))
    _sync_rng_to_state(state, rng)
    return state, event_instance, logs


def step(
    state: GameState,
    content: ContentBundle,
    policy: AutopickPolicy = "safe",
) -> tuple[GameState, EventInstance | None, list[LogEntry]]:
    state, event_instance, logs = advance_to_next_event(state, content)
    if event_instance is None:
        return state, None, logs

    rng = _rng_from_state(state)
    selected_option = _choose_option(policy, event_instance, rng)
    if selected_option is None:
        logs.append(make_log_entry(state, "system", "All event options are locked."))
        _sync_rng_to_state(state, rng)
        return state, event_instance, logs

    logs.extend(apply_choice(state, event_instance, selected_option.id, content, rng))
    _sync_rng_to_state(state, rng)
    return state, event_instance, logs


def run_simulation(
    initial_state: GameState,
    content: ContentBundle,
    steps: int,
    policy: AutopickPolicy = "safe",
) -> tuple[GameState, list[LogEntry]]:
    state = initial_state
    timeline: list[LogEntry] = []
    for _ in range(steps):
        if state.dead:
            break
        _, _, step_logs = step(state, content, policy)
        timeline.extend(step_logs)
    return state, timeline
