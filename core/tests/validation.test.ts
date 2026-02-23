import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { loadContent } from "../src/content/loader";

describe("content validation", () => {
  it("throws a helpful error when loot table references missing item", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "phase0-content-validation-"));
    const tempContentDir = path.join(tempRoot, "content");
    await mkdir(tempContentDir);

    const sourceContentDir = path.resolve(process.cwd(), "content");
    const files = ["items.json", "events.json", "biomes.json", "loottables.json"] as const;

    await Promise.all(
      files.map(async (file) => {
        const raw = await readFile(path.join(sourceContentDir, file), "utf8");
        await writeFile(path.join(tempContentDir, file), raw, "utf8");
      })
    );

    const lootTablesPath = path.join(tempContentDir, "loottables.json");
    const lootTables = JSON.parse(await readFile(lootTablesPath, "utf8")) as Array<{
      id: string;
      entries: Array<{ itemId: string; weight: number }>;
    }>;
    if (!lootTables[0]?.entries[0]) {
      throw new Error("Expected starter loottables.json to contain at least one entry.");
    }
    lootTables[0].entries[0].itemId = "missing_item_id";
    await writeFile(lootTablesPath, JSON.stringify(lootTables, null, 2), "utf8");

    await expect(loadContent(tempContentDir)).rejects.toThrow(/missing item 'missing_item_id'/i);

    await rm(tempRoot, { recursive: true, force: true });
  });
});
