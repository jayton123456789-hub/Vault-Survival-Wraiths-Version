import { z } from "zod";

export const MeterNameSchema = z.enum(["stamina", "hydration", "morale"]);
export type MeterName = z.infer<typeof MeterNameSchema>;

export const ItemSlotSchema = z.enum(["pack", "armor", "vehicle", "utility", "faction"]);
export type ItemSlot = z.infer<typeof ItemSlotSchema>;

export const ItemModifierSchema = z
  .object({
    speed: z.number().optional(),
    carry: z.number().optional(),
    injuryResist: z.number().optional(),
    staminaDrainMul: z.number().optional(),
    hydrationDrainMul: z.number().optional(),
    moraleMul: z.number().optional(),
    noise: z.number().optional()
  })
  .strict();

export const DurabilitySchema = z
  .object({
    max: z.number().positive(),
    current: z.number().nonnegative().optional()
  })
  .strict();

export const ItemSchema = z
  .object({
    id: z.string().min(1),
    name: z.string().min(1),
    slot: ItemSlotSchema,
    tags: z.array(z.string().min(1)),
    rarity: z.enum(["common", "uncommon", "rare", "legendary"]),
    modifiers: ItemModifierSchema,
    durability: DurabilitySchema.optional(),
    value: z.number().nonnegative().optional()
  })
  .strict();

export type Item = z.infer<typeof ItemSchema>;

export const LootTableEntrySchema = z
  .object({
    itemId: z.string().min(1),
    weight: z.number().positive(),
    min: z.number().int().positive().optional(),
    max: z.number().int().positive().optional()
  })
  .strict()
  .refine((entry) => (entry.max ?? entry.min ?? 1) >= (entry.min ?? 1), {
    message: "max must be greater than or equal to min"
  });

export const LootTableSchema = z
  .object({
    id: z.string().min(1),
    entries: z.array(LootTableEntrySchema).min(1),
    rolls: z.number().int().positive().optional(),
    guaranteed: z
      .array(
        z
          .object({
            itemId: z.string().min(1),
            qty: z.number().int().positive()
          })
          .strict()
      )
      .optional()
  })
  .strict();

export type LootTable = z.infer<typeof LootTableSchema>;

export const BiomeSchema = z
  .object({
    id: z.string().min(1),
    name: z.string().min(1),
    meterDrainMul: z
      .object({
        stamina: z.number().positive(),
        hydration: z.number().positive(),
        morale: z.number().positive()
      })
      .strict(),
    eventWeightMulByTag: z.record(z.string().min(1), z.number().positive()).optional(),
    lootTableIds: z.array(z.string().min(1))
  })
  .strict();

export type Biome = z.infer<typeof BiomeSchema>;

export type RequirementExpr =
  | { all: RequirementExpr[] }
  | { any: RequirementExpr[] }
  | { not: RequirementExpr }
  | { hasTag: string }
  | { hasItem: string }
  | { flag: string }
  | { meterGte: { meter: MeterName; value: number } }
  | { injuryLte: number }
  | { distanceGte: number };

const RequirementHasTagSchema = z.object({ hasTag: z.string().min(1) }).strict();
const RequirementHasItemSchema = z.object({ hasItem: z.string().min(1) }).strict();
const RequirementFlagSchema = z.object({ flag: z.string().min(1) }).strict();
const RequirementMeterSchema = z
  .object({
    meterGte: z
      .object({
        meter: MeterNameSchema,
        value: z.number()
      })
      .strict()
  })
  .strict();
const RequirementInjurySchema = z.object({ injuryLte: z.number() }).strict();
const RequirementDistanceSchema = z.object({ distanceGte: z.number() }).strict();

export const RequirementExprSchema: z.ZodType<RequirementExpr> = z.lazy(() =>
  z.union([
    z.object({ all: z.array(RequirementExprSchema).min(1) }).strict(),
    z.object({ any: z.array(RequirementExprSchema).min(1) }).strict(),
    z.object({ not: RequirementExprSchema }).strict(),
    RequirementHasTagSchema,
    RequirementHasItemSchema,
    RequirementFlagSchema,
    RequirementMeterSchema,
    RequirementInjurySchema,
    RequirementDistanceSchema
  ])
);

export type Outcome =
  | { addItems: Array<{ itemId: string; qty: number }> }
  | { removeItems: Array<{ itemId: string; qty: number }> }
  | { setFlags: string[] }
  | { unsetFlags: string[] }
  | { metersDelta: Partial<Record<MeterName, number>> }
  | { addInjury: number }
  | { setDeathChance: number }
  | { lootRoll: { lootTableId: string; rolls?: number } };

const ItemQtySchema = z
  .object({
    itemId: z.string().min(1),
    qty: z.number().int().positive()
  })
  .strict();

const MetersDeltaSchema = z
  .object({
    stamina: z.number().optional(),
    hydration: z.number().optional(),
    morale: z.number().optional()
  })
  .strict();

export const OutcomeSchema: z.ZodType<Outcome> = z.union([
  z.object({ addItems: z.array(ItemQtySchema).min(1) }).strict(),
  z.object({ removeItems: z.array(ItemQtySchema).min(1) }).strict(),
  z.object({ setFlags: z.array(z.string().min(1)).min(1) }).strict(),
  z.object({ unsetFlags: z.array(z.string().min(1)).min(1) }).strict(),
  z.object({ metersDelta: MetersDeltaSchema }).strict(),
  z.object({ addInjury: z.number() }).strict(),
  z.object({ setDeathChance: z.number().min(0).max(1) }).strict(),
  z
    .object({
      lootRoll: z
        .object({
          lootTableId: z.string().min(1),
          rolls: z.number().int().positive().optional()
        })
        .strict()
    })
    .strict()
]);

export const EventTriggerSchema = z
  .object({
    biomeIds: z.array(z.string().min(1)).optional(),
    minDistance: z.number().optional(),
    maxDistance: z.number().optional(),
    requiredFlagsAll: z.array(z.string().min(1)).optional(),
    forbiddenFlagsAny: z.array(z.string().min(1)).optional(),
    cooldownSteps: z.number().int().nonnegative().optional()
  })
  .strict();

export type EventTrigger = z.infer<typeof EventTriggerSchema>;

export const EventOptionSchema = z
  .object({
    id: z.string().min(1),
    label: z.string().min(1),
    requirements: RequirementExprSchema.optional(),
    costs: z.array(OutcomeSchema).optional(),
    outcomes: z.array(OutcomeSchema).min(1),
    logLine: z.string().min(1)
  })
  .strict();

export type EventOption = z.infer<typeof EventOptionSchema>;

export const EventSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    text: z.string().min(1),
    tags: z.array(z.string().min(1)),
    trigger: EventTriggerSchema,
    weight: z.number().positive(),
    options: z.array(EventOptionSchema).min(1)
  })
  .strict();

export type Event = z.infer<typeof EventSchema>;

export const ItemsFileSchema = z.array(ItemSchema);
export const LootTablesFileSchema = z.array(LootTableSchema);
export const BiomesFileSchema = z.array(BiomeSchema);
export const EventsFileSchema = z.array(EventSchema);
