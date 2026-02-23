import { LoadedContent } from "../content/loader";
import { Event, Outcome } from "../content/schemas";
import { nextInt } from "../rng/rng";

import { createLogEntry, LogEntry } from "./log";
import { applyOutcomes } from "./outcomes";
import { evaluateRequirement } from "./requirements";
import { selectEvent } from "./selector";
import { RunnerState, cloneRunnerState, decrementCooldowns } from "./state";
import { advanceTravel } from "./travel";

export type AutopickPolicy = "safe" | "random" | "greedy";

export interface EventOptionInstance {
  readonly id: string;
  readonly label: string;
  readonly locked: boolean;
  readonly lockReasons: string[];
  readonly costs: Outcome[];
  readonly outcomes: Outcome[];
  readonly logLine: string;
}

export interface EventInstance {
  readonly eventId: string;
  readonly title: string;
  readonly text: string;
  readonly tags: string[];
  readonly options: EventOptionInstance[];
}

export interface StepResult {
  readonly state: RunnerState;
  readonly event?: EventInstance;
  readonly logEntries: LogEntry[];
}

function instantiateEvent(event: Event, state: RunnerState, content: LoadedContent): EventInstance {
  const options: EventOptionInstance[] = event.options.map((option) => {
    if (!option.requirements) {
      return {
        id: option.id,
        label: option.label,
        locked: false,
        lockReasons: [],
        costs: option.costs ?? [],
        outcomes: option.outcomes,
        logLine: option.logLine
      };
    }

    const check = evaluateRequirement(option.requirements, state, content);
    return {
      id: option.id,
      label: option.label,
      locked: !check.ok,
      lockReasons: check.reasons,
      costs: option.costs ?? [],
      outcomes: option.outcomes,
      logLine: option.logLine
    };
  });

  return {
    eventId: event.id,
    title: event.title,
    text: event.text,
    tags: event.tags,
    options
  };
}

function scoreOption(option: EventOptionInstance, mode: Exclude<AutopickPolicy, "random">): number {
  const all = [...option.costs, ...option.outcomes];
  let score = 0;

  all.forEach((outcome) => {
    if ("addItems" in outcome) {
      const qty = outcome.addItems.reduce((sum, item) => sum + item.qty, 0);
      score += mode === "greedy" ? qty * 4 : qty * 2;
    }
    if ("removeItems" in outcome) {
      const qty = outcome.removeItems.reduce((sum, item) => sum + item.qty, 0);
      score -= mode === "greedy" ? qty * 1.5 : qty * 5;
    }
    if ("metersDelta" in outcome) {
      const values = [outcome.metersDelta.stamina, outcome.metersDelta.hydration, outcome.metersDelta.morale];
      values.forEach((value) => {
        if (typeof value !== "number") {
          return;
        }
        if (value >= 0) {
          score += mode === "greedy" ? value * 0.6 : value * 0.4;
        } else {
          score += mode === "greedy" ? value * 0.7 : value * 1.7;
        }
      });
    }
    if ("addInjury" in outcome) {
      score += mode === "greedy" ? -outcome.addInjury * 1.5 : -outcome.addInjury * 4;
    }
    if ("setDeathChance" in outcome) {
      score -= mode === "greedy" ? outcome.setDeathChance * 120 : outcome.setDeathChance * 800;
    }
    if ("lootRoll" in outcome) {
      score += mode === "greedy" ? 8 : 2;
    }
    if ("setFlags" in outcome) {
      score += mode === "greedy" ? outcome.setFlags.length * 1.5 : outcome.setFlags.length * 1;
    }
  });

  return score;
}

function chooseOption(
  policy: AutopickPolicy,
  event: EventInstance,
  state: RunnerState
): { state: RunnerState; optionId?: string } {
  const unlocked = event.options.filter((option) => !option.locked);
  if (unlocked.length === 0) {
    return { state };
  }

  if (policy === "random") {
    const next = cloneRunnerState(state);
    const sampled = nextInt(next.rng, 0, unlocked.length);
    next.rng = sampled.rng;
    const picked = unlocked[sampled.value];
    if (!picked) {
      return { state: next };
    }
    return { state: next, optionId: picked.id };
  }

  const scored = unlocked.map((option) => ({ option, score: scoreOption(option, policy) }));
  scored.sort((a, b) => b.score - a.score);
  const picked = scored[0];
  if (!picked) {
    return { state };
  }
  return { state, optionId: picked.option.id };
}

export function applyChoice(
  state: RunnerState,
  eventInstance: EventInstance,
  optionId: string,
  content: LoadedContent
): { state: RunnerState; logEntries: LogEntry[] } {
  const option = eventInstance.options.find((entry) => entry.id === optionId);
  if (!option) {
    throw new Error(`Option '${optionId}' was not found on event '${eventInstance.eventId}'.`);
  }
  if (option.locked) {
    return {
      state,
      logEntries: [
        createLogEntry(
          state,
          "system",
          `Choice '${option.label}' is locked: ${option.lockReasons.join("; ")}`
        )
      ]
    };
  }

  const logs: LogEntry[] = [createLogEntry(state, "choice", option.logLine)];
  let currentState = cloneRunnerState(state);

  if (option.costs.length > 0) {
    const costResult = applyOutcomes(currentState, option.costs, content);
    currentState = costResult.state;
    logs.push(...costResult.logEntries);
  }

  if (!currentState.dead) {
    const outcomeResult = applyOutcomes(currentState, option.outcomes, content);
    currentState = outcomeResult.state;
    logs.push(...outcomeResult.logEntries);
  }

  return {
    state: currentState,
    logEntries: logs
  };
}

export function step(
  state: RunnerState,
  content: LoadedContent,
  policy: AutopickPolicy = "safe"
): StepResult {
  let currentState = cloneRunnerState(state);
  currentState.eventCooldowns = decrementCooldowns(currentState.eventCooldowns);

  const logs: LogEntry[] = [];
  const travelResult = advanceTravel(currentState, content);
  currentState = travelResult.state;
  logs.push(...travelResult.logEntries);

  if (currentState.dead) {
    return { state: currentState, logEntries: logs };
  }

  const selected = selectEvent(currentState, content);
  currentState = selected.state;
  if (!selected.event) {
    logs.push(createLogEntry(currentState, "system", "No event triggered this step."));
    return { state: currentState, logEntries: logs };
  }

  const event = selected.event;
  if ((event.trigger.cooldownSteps ?? 0) > 0) {
    currentState.eventCooldowns[event.id] = event.trigger.cooldownSteps ?? 0;
  }

  const eventInstance = instantiateEvent(event, currentState, content);
  logs.push(createLogEntry(currentState, "event", `${event.title}: ${event.text}`));

  const choice = chooseOption(policy, eventInstance, currentState);
  currentState = choice.state;
  if (!choice.optionId) {
    logs.push(createLogEntry(currentState, "system", "All event options are locked."));
    return {
      state: currentState,
      event: eventInstance,
      logEntries: logs
    };
  }

  const outcome = applyChoice(currentState, eventInstance, choice.optionId, content);
  currentState = outcome.state;
  logs.push(...outcome.logEntries);

  return {
    state: currentState,
    event: eventInstance,
    logEntries: logs
  };
}
