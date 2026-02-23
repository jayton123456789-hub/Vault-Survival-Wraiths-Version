import { readFile } from "node:fs/promises";
import path from "node:path";

import { z } from "zod";

import {
  Biome,
  BiomesFileSchema,
  Event,
  EventsFileSchema,
  Item,
  ItemsFileSchema,
  LootTable,
  LootTablesFileSchema,
  Outcome,
  RequirementExpr
} from "./schemas";
import {
  ContentError,
  DuplicateIdError,
  assertReferenceExists,
  assertUniqueIds,
  indexById
} from "./refs";

const CONTENT_FILES = {
  items: "items.json",
  loottables: "loottables.json",
  biomes: "biomes.json",
  events: "events.json"
} as const;

export interface LoadedContent {
  readonly items: Item[];
  readonly loottables: LootTable[];
  readonly biomes: Biome[];
  readonly events: Event[];
  readonly itemById: Record<string, Item>;
  readonly lootTableById: Record<string, LootTable>;
  readonly biomeById: Record<string, Biome>;
  readonly eventById: Record<string, Event>;
}

export class ContentValidationError extends ContentError {
  public constructor(fileName: string, details: string[]) {
    super(`Validation failed for ${fileName}:\n${details.join("\n")}`, {
      fileName,
      details
    });
    this.name = "ContentValidationError";
  }
}

export class ContentParseError extends ContentError {
  public constructor(fileName: string, rawError: unknown) {
    const detail =
      rawError instanceof Error ? `${rawError.name}: ${rawError.message}` : String(rawError);
    super(`Failed to parse JSON in ${fileName}: ${detail}`, { fileName, detail });
    this.name = "ContentParseError";
  }
}

function formatZodIssues(issues: z.ZodIssue[]): string[] {
  return issues.map((issue) => {
    const pathText = issue.path.length > 0 ? issue.path.join(".") : "(root)";
    return `- ${pathText}: ${issue.message}`;
  });
}

async function readJson(filePath: string): Promise<unknown> {
  const raw = await readFile(filePath, "utf8");
  try {
    return JSON.parse(raw) as unknown;
  } catch (error) {
    throw new ContentParseError(path.basename(filePath), error);
  }
}

async function loadAndValidate<T>(
  contentDir: string,
  fileName: string,
  schema: z.ZodType<T>
): Promise<T> {
  const fullPath = path.join(contentDir, fileName);
  const data = await readJson(fullPath);
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    throw new ContentValidationError(fileName, formatZodIssues(parsed.error.issues));
  }
  return parsed.data;
}

function validateRequirementRefs(
  requirement: RequirementExpr,
  eventId: string,
  optionId: string,
  itemById: Record<string, Item>,
  pathParts: string[] = []
): void {
  if ("hasItem" in requirement) {
    assertReferenceExists({
      sourceType: "event",
      sourceId: eventId,
      fieldPath: `options[${optionId}].requirements.${[...pathParts, "hasItem"].join(".")}`,
      targetType: "item",
      targetId: requirement.hasItem,
      exists: Boolean(itemById[requirement.hasItem])
    });
    return;
  }
  if ("all" in requirement) {
    requirement.all.forEach((child, index) =>
      validateRequirementRefs(child, eventId, optionId, itemById, [...pathParts, `all[${index}]`])
    );
    return;
  }
  if ("any" in requirement) {
    requirement.any.forEach((child, index) =>
      validateRequirementRefs(child, eventId, optionId, itemById, [...pathParts, `any[${index}]`])
    );
    return;
  }
  if ("not" in requirement) {
    validateRequirementRefs(requirement.not, eventId, optionId, itemById, [...pathParts, "not"]);
  }
}

function validateOutcomeRefs(
  outcomes: Outcome[],
  sourceType: "costs" | "outcomes",
  eventId: string,
  optionId: string,
  itemById: Record<string, Item>,
  lootTableById: Record<string, LootTable>
): void {
  outcomes.forEach((outcome, outcomeIndex) => {
    if ("addItems" in outcome) {
      outcome.addItems.forEach((entry, entryIndex) => {
        assertReferenceExists({
          sourceType: "event",
          sourceId: eventId,
          fieldPath: `options[${optionId}].${sourceType}[${outcomeIndex}].addItems[${entryIndex}].itemId`,
          targetType: "item",
          targetId: entry.itemId,
          exists: Boolean(itemById[entry.itemId])
        });
      });
    }
    if ("removeItems" in outcome) {
      outcome.removeItems.forEach((entry, entryIndex) => {
        assertReferenceExists({
          sourceType: "event",
          sourceId: eventId,
          fieldPath: `options[${optionId}].${sourceType}[${outcomeIndex}].removeItems[${entryIndex}].itemId`,
          targetType: "item",
          targetId: entry.itemId,
          exists: Boolean(itemById[entry.itemId])
        });
      });
    }
    if ("lootRoll" in outcome) {
      assertReferenceExists({
        sourceType: "event",
        sourceId: eventId,
        fieldPath: `options[${optionId}].${sourceType}[${outcomeIndex}].lootRoll.lootTableId`,
        targetType: "loottable",
        targetId: outcome.lootRoll.lootTableId,
        exists: Boolean(lootTableById[outcome.lootRoll.lootTableId])
      });
    }
  });
}

function validateAndResolveRefs(
  items: Item[],
  loottables: LootTable[],
  biomes: Biome[],
  events: Event[]
): LoadedContent {
  assertUniqueIds("item", items);
  assertUniqueIds("loottable", loottables);
  assertUniqueIds("biome", biomes);
  assertUniqueIds("event", events);

  const itemById = indexById(items);
  const lootTableById = indexById(loottables);
  const biomeById = indexById(biomes);
  const eventById = indexById(events);

  loottables.forEach((table) => {
    table.entries.forEach((entry, index) =>
      assertReferenceExists({
        sourceType: "loottable",
        sourceId: table.id,
        fieldPath: `entries[${index}].itemId`,
        targetType: "item",
        targetId: entry.itemId,
        exists: Boolean(itemById[entry.itemId])
      })
    );
    table.guaranteed?.forEach((entry, index) =>
      assertReferenceExists({
        sourceType: "loottable",
        sourceId: table.id,
        fieldPath: `guaranteed[${index}].itemId`,
        targetType: "item",
        targetId: entry.itemId,
        exists: Boolean(itemById[entry.itemId])
      })
    );
  });

  biomes.forEach((biome) => {
    biome.lootTableIds.forEach((lootTableId, index) =>
      assertReferenceExists({
        sourceType: "biome",
        sourceId: biome.id,
        fieldPath: `lootTableIds[${index}]`,
        targetType: "loottable",
        targetId: lootTableId,
        exists: Boolean(lootTableById[lootTableId])
      })
    );
  });

  events.forEach((event) => {
    event.trigger.biomeIds?.forEach((biomeId, index) =>
      assertReferenceExists({
        sourceType: "event",
        sourceId: event.id,
        fieldPath: `trigger.biomeIds[${index}]`,
        targetType: "biome",
        targetId: biomeId,
        exists: Boolean(biomeById[biomeId])
      })
    );

    const optionIds = new Set<string>();
    event.options.forEach((option) => {
      if (optionIds.has(option.id)) {
        throw new DuplicateIdError(`event:${event.id}.option`, option.id);
      }
      optionIds.add(option.id);

      if (option.requirements) {
        validateRequirementRefs(option.requirements, event.id, option.id, itemById);
      }
      if (option.costs) {
        validateOutcomeRefs(option.costs, "costs", event.id, option.id, itemById, lootTableById);
      }
      validateOutcomeRefs(option.outcomes, "outcomes", event.id, option.id, itemById, lootTableById);
    });
  });

  return {
    items,
    loottables,
    biomes,
    events,
    itemById,
    lootTableById,
    biomeById,
    eventById
  };
}

export async function loadContent(contentDir = path.resolve(process.cwd(), "content")): Promise<LoadedContent> {
  const [items, loottables, biomes, events] = await Promise.all([
    loadAndValidate(contentDir, CONTENT_FILES.items, ItemsFileSchema),
    loadAndValidate(contentDir, CONTENT_FILES.loottables, LootTablesFileSchema),
    loadAndValidate(contentDir, CONTENT_FILES.biomes, BiomesFileSchema),
    loadAndValidate(contentDir, CONTENT_FILES.events, EventsFileSchema)
  ]);

  return validateAndResolveRefs(items, loottables, biomes, events);
}
