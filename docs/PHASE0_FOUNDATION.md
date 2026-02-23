# Phase 0 Foundation

## Pipeline
1. `tools/simulate.ts` loads JSON content from `/content`.
2. `core/src/content/loader.ts` validates shape with Zod schemas and resolves references.
3. Deterministic sim loop (`core/src/sim/engine.ts`) runs:
   - decrement cooldowns
   - travel and meter drain
   - event filter + weighted deterministic selection
   - option lock evaluation (requirements)
   - autopick choice (`safe`, `random`, `greedy`)
   - costs then outcomes
4. Timeline logs are generated for every state transition and printed by CLI.

## Determinism Rules
- RNG is seeded from `seed` and advanced only through `nextFloat`, `nextInt`, and weighted picks.
- All weighted/event/item selection uses deterministic iteration order from content arrays.
- No wall-clock time, random global state, or non-deterministic APIs are used.
- Same content + seed + policy + step count yields the same timeline and final state.

## Schema Surface (Short)
- `items.json`: item definitions with slots, tags, rarity, modifiers, optional durability/value.
- `loottables.json`: weighted entries, optional guaranteed entries, default roll count.
- `biomes.json`: per-meter drain multipliers, optional event tag multipliers, referenced loot tables.
- `events.json`: trigger conditions, weighted selection, option requirements, costs, and outcomes.
- Requirements support boolean composition (`all/any/not`) and leaf checks (`hasTag`, `hasItem`, `flag`, meter/injury/distance checks).
- Outcomes support item add/remove, flag set/unset, meter delta, injury delta, death chance, and loot rolls.

## Requirement Behavior Notes
- `hasItem` checks both inventory and equipped slots.
- `hasTag` checks tags on currently owned items (inventory + equipped).

## CLI
Run headless simulation:

```bash
pnpm sim --seed 42 --steps 30 --biome suburbs --autopick safe
```

Arguments:
- `--seed <n|string>`
- `--steps <n>`
- `--biome <id>`
- `--autopick <safe|random|greedy>`

## Tests
Run test suite:

```bash
pnpm test
```

Included tests:
- determinism (`core/tests/determinism.test.ts`)
- content validation failures (`core/tests/validation.test.ts`)
- 30-step smoke run (`core/tests/sim_smoke.test.ts`)
