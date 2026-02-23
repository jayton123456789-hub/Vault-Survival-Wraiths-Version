import { createHash } from "node:crypto";
import path from "node:path";

import { loadContent } from "../core/src/content/loader";
import { AutopickPolicy, step } from "../core/src/sim/engine";
import { formatLogEntry } from "../core/src/sim/log";
import { createInitialRunnerState } from "../core/src/sim/state";

interface CliArgs {
  seed: number | string;
  steps: number;
  biome?: string;
  autopick: AutopickPolicy;
}

function parseArgs(argv: string[]): CliArgs {
  const parsed: CliArgs = {
    seed: 1337,
    steps: 30,
    autopick: "safe"
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--seed") {
      const next = argv[index + 1];
      if (!next) {
        throw new Error("--seed requires a value.");
      }
      const numeric = Number(next);
      parsed.seed = Number.isFinite(numeric) && !Number.isNaN(numeric) ? numeric : next;
      index += 1;
      continue;
    }
    if (token === "--steps") {
      const next = argv[index + 1];
      if (!next) {
        throw new Error("--steps requires a value.");
      }
      const numeric = Number(next);
      if (!Number.isInteger(numeric) || numeric <= 0) {
        throw new Error(`--steps must be a positive integer. Received: ${next}`);
      }
      parsed.steps = numeric;
      index += 1;
      continue;
    }
    if (token === "--biome") {
      const next = argv[index + 1];
      if (!next) {
        throw new Error("--biome requires a biome id.");
      }
      parsed.biome = next;
      index += 1;
      continue;
    }
    if (token === "--autopick") {
      const next = argv[index + 1];
      if (!next || !["safe", "random", "greedy"].includes(next)) {
        throw new Error("--autopick must be one of: safe, random, greedy.");
      }
      parsed.autopick = next as AutopickPolicy;
      index += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${token}`);
  }

  return parsed;
}

function deterministicSignature(
  payload: Record<string, unknown>,
  logLines: string[]
): string {
  return createHash("sha256")
    .update(JSON.stringify({ payload, logLines }))
    .digest("hex")
    .slice(0, 16);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const contentDir = path.resolve(process.cwd(), "content");
  const content = await loadContent(contentDir);

  const biomeId = args.biome ?? content.biomes[0]?.id;
  if (!biomeId) {
    throw new Error("No biome available in content.");
  }
  if (!content.biomeById[biomeId]) {
    throw new Error(`Unknown biome '${biomeId}'.`);
  }

  let state = createInitialRunnerState(args.seed, biomeId);
  const allLogs: string[] = [];

  for (let index = 0; index < args.steps; index += 1) {
    if (state.dead) {
      break;
    }
    const result = step(state, content, args.autopick);
    state = result.state;
    result.logEntries.forEach((entry) => {
      const line = formatLogEntry(entry);
      allLogs.push(line);
      // eslint-disable-next-line no-console
      console.log(line);
    });
  }

  const inventorySummary = Object.entries(state.inventory)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([itemId, qty]) => `${itemId}x${qty}`)
    .join(", ");
  const flagsSummary = [...state.flags].sort().join(", ");

  // eslint-disable-next-line no-console
  console.log("\n--- Final Summary ---");
  // eslint-disable-next-line no-console
  console.log(`seed=${state.seed} autopick=${args.autopick} steps=${state.step}/${args.steps}`);
  // eslint-disable-next-line no-console
  console.log(`distance=${state.distance.toFixed(2)} time=${state.time} biome=${state.biomeId}`);
  // eslint-disable-next-line no-console
  console.log(
    `meters={stamina:${state.meters.stamina.toFixed(2)}, hydration:${state.meters.hydration.toFixed(
      2
    )}, morale:${state.meters.morale.toFixed(2)}} injury=${state.injury.toFixed(2)}`
  );
  // eslint-disable-next-line no-console
  console.log(`dead=${state.dead}${state.deathReason ? ` reason=${state.deathReason}` : ""}`);
  // eslint-disable-next-line no-console
  console.log(`flags=[${flagsSummary}]`);
  // eslint-disable-next-line no-console
  console.log(`inventory=[${inventorySummary}]`);

  const signature = deterministicSignature(
    {
      seed: state.seed,
      autopick: args.autopick,
      distance: state.distance,
      step: state.step,
      dead: state.dead,
      deathReason: state.deathReason,
      meters: state.meters,
      injury: state.injury,
      biome: state.biomeId,
      flags: [...state.flags].sort(),
      inventory: Object.entries(state.inventory).sort((a, b) => a[0].localeCompare(b[0]))
    },
    allLogs
  );

  // eslint-disable-next-line no-console
  console.log(`signature=${signature}`);
}

void main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
