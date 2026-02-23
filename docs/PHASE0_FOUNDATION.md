# Phase 0 Foundation (Python)

## Scope
Phase 0 implements engine/core foundations only:
- Data-driven content in JSON
- Deterministic run simulation
- Validation + reference resolution
- Headless CLI simulator
- Unit tests for determinism, validation, and smoke execution

## Pipeline
1. `bit_life_survival/core/loader.py` loads JSON files from `bit_life_survival/content`.
2. Pydantic validates schema shape for items, events, biomes, and loot tables.
3. Reference resolution validates IDs (`itemId`, `lootTableId`, `biomeIds`, etc.) with clear failures.
4. Simulation engine (`core/engine.py`) runs step loop:
   - decrement cooldowns
   - travel drain/update (`core/travel.py`)
   - event selection (`core/selector.py`)
   - requirements locking (`core/requirements.py`)
   - autopick choice (`safe|random|greedy`)
   - costs/outcomes (`core/outcomes.py`)

## Determinism Rules
- RNG uses internal xorshift state from a seed hash (`core/rng.py`), not Python global randomness.
- All weighted picks and integer draws come from that deterministic RNG state.
- Same content + seed + autopick policy + step count produces identical logs and final state.
- Signature hashing in CLI uses canonical sorted payload data.

## Data Model Summary
- `Item`: slot/tags/rarity/modifiers/durability/value
- `LootTable`: weighted entries + guaranteed rolls
- `Biome`: meter drain multipliers + event tag multipliers
- `Event`: trigger filters + weighted options with requirements/costs/outcomes
- `GameState`: runner meters, injury, flags, inventory, equipment, cooldowns, RNG state
- `VaultState`: storage, blueprints, upgrades, tav, vault level, citizen queue

## Run CLI
```bash
python -m bit_life_survival.tools.simulate --seed 123 --steps 50 --biome suburbs --autopick safe
```

## Run Tests
```bash
pytest bit_life_survival/tests
```
