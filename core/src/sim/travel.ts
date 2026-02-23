import { LoadedContent } from "../content/loader";

import { createLogEntry, LogEntry } from "./log";
import { RunnerState, cloneRunnerState, normalizeMeter } from "./state";

export const BASE_SPEED = 1;
export const BASE_DRAIN = {
  stamina: 4,
  hydration: 5,
  morale: 1.5
} as const;
export const INJURY_DEATH_THRESHOLD = 100;

function equippedItems(state: RunnerState, content: LoadedContent) {
  return Object.values(state.equipped)
    .map((itemId) => (itemId ? content.itemById[itemId] : undefined))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
}

function drainMultiplier(items: ReturnType<typeof equippedItems>, key: "staminaDrainMul" | "hydrationDrainMul" | "moraleMul"): number {
  return items.reduce((acc, item) => {
    const value = item.modifiers[key];
    return acc * (value ?? 1);
  }, 1);
}

export function applyDeathChecks(state: RunnerState): RunnerState {
  if (state.dead) {
    return state;
  }
  if (state.meters.hydration <= 0) {
    return {
      ...state,
      dead: true,
      deathReason: "Dehydration"
    };
  }
  if (state.meters.stamina <= 0) {
    return {
      ...state,
      dead: true,
      deathReason: "Exhaustion"
    };
  }
  if (state.injury >= INJURY_DEATH_THRESHOLD) {
    return {
      ...state,
      dead: true,
      deathReason: "Critical injury"
    };
  }
  return state;
}

export function advanceTravel(state: RunnerState, content: LoadedContent): { state: RunnerState; logEntries: LogEntry[] } {
  if (state.dead) {
    return {
      state,
      logEntries: [createLogEntry(state, "system", "Travel skipped because runner is dead.")]
    };
  }

  const biome = content.biomeById[state.biomeId];
  if (!biome) {
    throw new Error(`Unknown biome '${state.biomeId}' in runner state.`);
  }

  const next = cloneRunnerState(state);
  const items = equippedItems(next, content);
  const speedBonus = items.reduce((sum, item) => sum + (item.modifiers.speed ?? 0), 0);
  const distanceDelta = Math.max(0, BASE_SPEED * (1 + speedBonus));

  const staminaDrain = BASE_DRAIN.stamina * biome.meterDrainMul.stamina * drainMultiplier(items, "staminaDrainMul");
  const hydrationDrain =
    BASE_DRAIN.hydration * biome.meterDrainMul.hydration * drainMultiplier(items, "hydrationDrainMul");
  const moraleDrain = BASE_DRAIN.morale * biome.meterDrainMul.morale * drainMultiplier(items, "moraleMul");

  next.step += 1;
  next.time += 1;
  next.distance += distanceDelta;
  next.meters.stamina = normalizeMeter(next.meters.stamina - staminaDrain);
  next.meters.hydration = normalizeMeter(next.meters.hydration - hydrationDrain);
  next.meters.morale = normalizeMeter(next.meters.morale - moraleDrain);

  const logs: LogEntry[] = [
    createLogEntry(
      next,
      "travel",
      `Travelled ${distanceDelta.toFixed(2)} in '${biome.id}' (stamina -${staminaDrain.toFixed(
        2
      )}, hydration -${hydrationDrain.toFixed(2)}, morale -${moraleDrain.toFixed(2)}).`
    )
  ];

  const checked = applyDeathChecks(next);
  if (checked.dead) {
    logs.push(createLogEntry(checked, "death", `Runner died: ${checked.deathReason ?? "Unknown cause"}.`));
  }
  return {
    state: checked,
    logEntries: logs
  };
}
