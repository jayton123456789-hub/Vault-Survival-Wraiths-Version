import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadContent } from "../src/content/loader";
import { step } from "../src/sim/engine";
import { createInitialRunnerState } from "../src/sim/state";

describe("sim smoke", () => {
  it("runs 30 steps without crashing and emits logs", async () => {
    const content = await loadContent(path.resolve(process.cwd(), "content"));
    let state = createInitialRunnerState(9991, "suburbs");
    let totalLogs = 0;

    for (let index = 0; index < 30; index += 1) {
      if (state.dead) {
        break;
      }
      const result = step(state, content, "safe");
      state = result.state;
      totalLogs += result.logEntries.length;
    }

    expect(totalLogs).toBeGreaterThan(0);
    expect(state.step).toBeGreaterThan(0);
  });
});
