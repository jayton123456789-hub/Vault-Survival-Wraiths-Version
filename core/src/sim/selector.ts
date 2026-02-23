import { LoadedContent } from "../content/loader";
import { Event } from "../content/schemas";
import { pickWeighted } from "../rng/rng";

import { RunnerState, cloneRunnerState } from "./state";

function eventMatchesTrigger(event: Event, state: RunnerState): boolean {
  const trigger = event.trigger;

  if (trigger.biomeIds && !trigger.biomeIds.includes(state.biomeId)) {
    return false;
  }
  if (typeof trigger.minDistance === "number" && state.distance < trigger.minDistance) {
    return false;
  }
  if (typeof trigger.maxDistance === "number" && state.distance > trigger.maxDistance) {
    return false;
  }
  if (trigger.requiredFlagsAll && trigger.requiredFlagsAll.some((flag) => !state.flags.has(flag))) {
    return false;
  }
  if (trigger.forbiddenFlagsAny && trigger.forbiddenFlagsAny.some((flag) => state.flags.has(flag))) {
    return false;
  }
  if ((state.eventCooldowns[event.id] ?? 0) > 0) {
    return false;
  }
  return true;
}

function effectiveWeight(event: Event, state: RunnerState, content: LoadedContent): number {
  const biome = content.biomeById[state.biomeId];
  if (!biome) {
    return 0;
  }

  const multipliers = biome.eventWeightMulByTag;
  if (!multipliers || event.tags.length === 0) {
    return event.weight;
  }

  return event.tags.reduce((weight, tag) => {
    const multiplier = multipliers[tag];
    return weight * (multiplier ?? 1);
  }, event.weight);
}

export function selectEvent(
  state: RunnerState,
  content: LoadedContent
): { state: RunnerState; event?: Event } {
  if (state.dead) {
    return { state };
  }

  const eligible = content.events
    .filter((event) => eventMatchesTrigger(event, state))
    .map((event) => ({
      event,
      weight: effectiveWeight(event, state, content)
    }))
    .filter((entry) => entry.weight > 0);

  if (eligible.length === 0) {
    return { state };
  }

  const next = cloneRunnerState(state);
  const picked = pickWeighted(
    next.rng,
    eligible.map((entry) => ({
      value: entry.event,
      weight: entry.weight
    }))
  );
  next.rng = picked.rng;

  return {
    state: next,
    event: picked.value
  };
}
