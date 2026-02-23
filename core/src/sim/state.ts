import { createRngState, RngState } from "../rng/rng";
import { ItemSlot, MeterName } from "../content/schemas";

export type MeterState = Record<MeterName, number>;
export type EquippedState = Record<ItemSlot, string | null>;

export interface RunnerState {
  seed: number | string;
  step: number;
  distance: number;
  time: number;
  biomeId: string;
  meters: MeterState;
  injury: number;
  flags: Set<string>;
  inventory: Record<string, number>;
  equipped: EquippedState;
  dead: boolean;
  deathReason?: string;
  eventCooldowns: Record<string, number>;
  rng: RngState;
}

export interface VaultState {
  storage: Record<string, number>;
  blueprints: Set<string>;
  upgrades: Record<string, number>;
  tav: number;
  vaultLevel: number;
}

export const DEFAULT_METERS: MeterState = {
  stamina: 100,
  hydration: 100,
  morale: 100
};

export const DEFAULT_EQUIPPED: EquippedState = {
  pack: null,
  armor: null,
  vehicle: null,
  utility: null,
  faction: null
};

export function createInitialRunnerState(seed: number | string, biomeId: string): RunnerState {
  return {
    seed,
    step: 0,
    distance: 0,
    time: 0,
    biomeId,
    meters: { ...DEFAULT_METERS },
    injury: 0,
    flags: new Set<string>(),
    inventory: {},
    equipped: { ...DEFAULT_EQUIPPED },
    dead: false,
    eventCooldowns: {},
    rng: createRngState(seed)
  };
}

export function createDefaultVaultState(): VaultState {
  return {
    storage: {},
    blueprints: new Set<string>(),
    upgrades: {},
    tav: 0,
    vaultLevel: 1
  };
}

export function cloneRunnerState(state: RunnerState): RunnerState {
  const clonedFlags = new Set<string>();
  state.flags.forEach((flag) => clonedFlags.add(flag));

  return {
    ...state,
    meters: { ...state.meters },
    flags: clonedFlags,
    inventory: { ...state.inventory },
    equipped: { ...state.equipped },
    eventCooldowns: { ...state.eventCooldowns }
  };
}

export function normalizeMeter(value: number): number {
  if (value <= 0) {
    return 0;
  }
  if (value >= 100) {
    return 100;
  }
  return value;
}

export function ownsItem(state: RunnerState, itemId: string): boolean {
  if ((state.inventory[itemId] ?? 0) > 0) {
    return true;
  }
  return Object.values(state.equipped).some((equippedItemId) => equippedItemId === itemId);
}

export function ownedItemIds(state: RunnerState): string[] {
  const ids = new Set<string>();
  Object.entries(state.inventory).forEach(([itemId, qty]) => {
    if (qty > 0) {
      ids.add(itemId);
    }
  });
  Object.values(state.equipped).forEach((itemId) => {
    if (itemId) {
      ids.add(itemId);
    }
  });
  return [...ids];
}

export function decrementCooldowns(cooldowns: Record<string, number>): Record<string, number> {
  const next: Record<string, number> = {};
  for (const [eventId, value] of Object.entries(cooldowns)) {
    const remaining = value - 1;
    if (remaining > 0) {
      next[eventId] = remaining;
    }
  }
  return next;
}
