import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadContent } from "../src/content/loader";
import { step } from "../src/sim/engine";
import { formatLogEntry } from "../src/sim/log";
import { createInitialRunnerState } from "../src/sim/state";

async function runDeterministicSimulation(seed: number | string, steps: number) {
  const content = await loadContent(path.resolve(process.cwd(), "content"));
  let state = createInitialRunnerState(seed, "suburbs");
  const timeline: string[] = [];

  for (let i = 0; i < steps; i += 1) {
    if (state.dead) {
      break;
    }
    const result = step(state, content, "safe");
    state = result.state;
    result.logEntries.forEach((entry) => timeline.push(formatLogEntry(entry)));
  }

  return {
    state,
    timeline
  };
}

describe("deterministic simulation", () => {
  it("produces identical results for same seed and policy", async () => {
    const firstRun = await runDeterministicSimulation(777, 25);
    const secondRun = await runDeterministicSimulation(777, 25);

    expect(firstRun.state.distance).toBe(secondRun.state.distance);
    expect(firstRun.state.step).toBe(secondRun.state.step);
    expect(firstRun.state.dead).toBe(secondRun.state.dead);
    expect(firstRun.timeline).toEqual(secondRun.timeline);
  });
});
