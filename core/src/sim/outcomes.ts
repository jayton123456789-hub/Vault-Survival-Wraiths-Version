import { LoadedContent } from "../content/loader";
import { Outcome } from "../content/schemas";
import { nextFloat, nextInt, pickWeighted } from "../rng/rng";

import { createLogEntry, LogEntry } from "./log";
import { RunnerState, cloneRunnerState, normalizeMeter } from "./state";
import { applyDeathChecks } from "./travel";

function addInventoryItem(inventory: Record<string, number>, itemId: string, qty: number): void {
  const current = inventory[itemId] ?? 0;
  inventory[itemId] = current + qty;
}

function removeInventoryItem(inventory: Record<string, number>, itemId: string, qty: number): number {
  const current = inventory[itemId] ?? 0;
  const removed = Math.min(current, qty);
  const next = current - removed;
  if (next <= 0) {
    delete inventory[itemId];
  } else {
    inventory[itemId] = next;
  }
  return removed;
}

function totalInjuryResistance(state: RunnerState, content: LoadedContent): number {
  const rawResistance = Object.values(state.equipped).reduce((sum, itemId) => {
    if (!itemId) {
      return sum;
    }
    const item = content.itemById[itemId];
    return sum + (item?.modifiers.injuryResist ?? 0);
  }, 0);
  return Math.max(0, Math.min(0.95, rawResistance));
}

function checkAndLogDeath(nextState: RunnerState, logEntries: LogEntry[]): RunnerState {
  const checked = applyDeathChecks(nextState);
  if (checked.dead && !nextState.dead) {
    logEntries.push(createLogEntry(checked, "death", `Runner died: ${checked.deathReason ?? "Unknown cause"}.`));
  }
  return checked;
}

export function applyOutcomes(
  state: RunnerState,
  outcomes: Outcome[],
  content: LoadedContent
): { state: RunnerState; logEntries: LogEntry[] } {
  const next = cloneRunnerState(state);
  const logs: LogEntry[] = [];

  for (const outcome of outcomes) {
    if (next.dead) {
      break;
    }

    if ("addItems" in outcome) {
      outcome.addItems.forEach((entry) => {
        addInventoryItem(next.inventory, entry.itemId, entry.qty);
        logs.push(createLogEntry(next, "outcome", `Gained ${entry.qty}x ${entry.itemId}.`));
      });
      continue;
    }

    if ("removeItems" in outcome) {
      outcome.removeItems.forEach((entry) => {
        let remaining = entry.qty;
        const removedFromInventory = removeInventoryItem(next.inventory, entry.itemId, remaining);
        remaining -= removedFromInventory;

        if (remaining > 0) {
          for (const [slot, equippedItemId] of Object.entries(next.equipped)) {
            if (equippedItemId === entry.itemId && remaining > 0) {
              next.equipped[slot as keyof typeof next.equipped] = null;
              remaining -= 1;
            }
          }
        }

        const removed = entry.qty - remaining;
        logs.push(createLogEntry(next, "outcome", `Removed ${removed}x ${entry.itemId}.`));
      });
      continue;
    }

    if ("setFlags" in outcome) {
      outcome.setFlags.forEach((flag) => next.flags.add(flag));
      logs.push(createLogEntry(next, "outcome", `Flags set: ${outcome.setFlags.join(", ")}.`));
      continue;
    }

    if ("unsetFlags" in outcome) {
      outcome.unsetFlags.forEach((flag) => next.flags.delete(flag));
      logs.push(createLogEntry(next, "outcome", `Flags cleared: ${outcome.unsetFlags.join(", ")}.`));
      continue;
    }

    if ("metersDelta" in outcome) {
      const deltas = outcome.metersDelta;
      if (typeof deltas.stamina === "number") {
        next.meters.stamina = normalizeMeter(next.meters.stamina + deltas.stamina);
      }
      if (typeof deltas.hydration === "number") {
        next.meters.hydration = normalizeMeter(next.meters.hydration + deltas.hydration);
      }
      if (typeof deltas.morale === "number") {
        next.meters.morale = normalizeMeter(next.meters.morale + deltas.morale);
      }
      logs.push(
        createLogEntry(
          next,
          "outcome",
          `Meters changed: stamina ${deltas.stamina ?? 0}, hydration ${deltas.hydration ?? 0}, morale ${
            deltas.morale ?? 0
          }.`
        )
      );
      continue;
    }

    if ("addInjury" in outcome) {
      const value = outcome.addInjury;
      const resist = totalInjuryResistance(next, content);
      const effective = value >= 0 ? value * (1 - resist) : value;
      next.injury = Math.max(0, next.injury + effective);
      logs.push(
        createLogEntry(
          next,
          "outcome",
          `Injury changed by ${effective.toFixed(2)} (raw ${value.toFixed(2)}, resist ${(resist * 100).toFixed(0)}%).`
        )
      );
      continue;
    }

    if ("setDeathChance" in outcome) {
      const chance = outcome.setDeathChance;
      const roll = nextFloat(next.rng);
      next.rng = roll.rng;
      if (roll.value < chance) {
        next.dead = true;
        next.deathReason = `Fatal outcome roll (${Math.round(chance * 100)}% chance).`;
        logs.push(
          createLogEntry(next, "death", `Death chance triggered at ${(chance * 100).toFixed(1)}% (roll ${roll.value.toFixed(4)}).`)
        );
      } else {
        logs.push(
          createLogEntry(next, "outcome", `Survived death chance ${(chance * 100).toFixed(1)}% (roll ${roll.value.toFixed(4)}).`)
        );
      }
      continue;
    }

    if ("lootRoll" in outcome) {
      const table = content.lootTableById[outcome.lootRoll.lootTableId];
      if (!table) {
        throw new Error(`Missing loot table '${outcome.lootRoll.lootTableId}' during outcome application.`);
      }
      const rolls = outcome.lootRoll.rolls ?? table.rolls ?? 1;

      table.guaranteed?.forEach((entry) => {
        addInventoryItem(next.inventory, entry.itemId, entry.qty);
        logs.push(createLogEntry(next, "outcome", `Guaranteed loot: ${entry.qty}x ${entry.itemId}.`));
      });

      for (let index = 0; index < rolls; index += 1) {
        const sample = pickWeighted(
          next.rng,
          table.entries.map((entry) => ({ value: entry, weight: entry.weight }))
        );
        next.rng = sample.rng;
        const pickedEntry = sample.value;

        const min = pickedEntry.min ?? 1;
        const max = pickedEntry.max ?? min;
        let qty = min;
        if (max > min) {
          const sampledQty = nextInt(next.rng, min, max + 1);
          next.rng = sampledQty.rng;
          qty = sampledQty.value;
        }

        addInventoryItem(next.inventory, pickedEntry.itemId, qty);
        logs.push(createLogEntry(next, "outcome", `Loot roll: ${qty}x ${pickedEntry.itemId}.`));
      }
    }
  }

  const checked = checkAndLogDeath(next, logs);
  return {
    state: checked,
    logEntries: logs
  };
}
