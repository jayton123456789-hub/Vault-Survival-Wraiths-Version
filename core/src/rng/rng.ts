export interface RngState {
  seed: string;
  state: number;
  calls: number;
}

export interface WeightedEntry<T> {
  value: T;
  weight: number;
}

function hashSeed(seed: number | string): number {
  const text = String(seed);
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) || 0x9e3779b9;
}

function nextUint32(state: number): number {
  let value = state >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  value >>>= 0;
  return value || 0x6d2b79f5;
}

export function createRngState(seed: number | string): RngState {
  return {
    seed: String(seed),
    state: hashSeed(seed),
    calls: 0
  };
}

export function nextFloat(rng: RngState): { value: number; rng: RngState } {
  const nextState = nextUint32(rng.state);
  return {
    value: nextState / 0x1_0000_0000,
    rng: {
      seed: rng.seed,
      state: nextState,
      calls: rng.calls + 1
    }
  };
}

export function nextInt(
  rng: RngState,
  minInclusive: number,
  maxExclusive: number
): { value: number; rng: RngState } {
  if (!Number.isInteger(minInclusive) || !Number.isInteger(maxExclusive)) {
    throw new Error("nextInt requires integer bounds.");
  }
  if (maxExclusive <= minInclusive) {
    throw new Error(
      `nextInt requires maxExclusive (${maxExclusive}) to be greater than minInclusive (${minInclusive}).`
    );
  }

  const span = maxExclusive - minInclusive;
  const { value, rng: nextRng } = nextFloat(rng);
  const sampled = minInclusive + Math.floor(value * span);
  return { value: sampled, rng: nextRng };
}

export function pickWeighted<T>(
  rng: RngState,
  entries: readonly WeightedEntry<T>[]
): { value: T; rng: RngState } {
  const validEntries = entries.filter((entry) => entry.weight > 0);
  if (validEntries.length === 0) {
    throw new Error("pickWeighted requires at least one entry with positive weight.");
  }

  const totalWeight = validEntries.reduce((sum, entry) => sum + entry.weight, 0);
  const { value: roll, rng: nextRng } = nextFloat(rng);
  let cursor = roll * totalWeight;
  for (const entry of validEntries) {
    if (cursor < entry.weight) {
      return { value: entry.value, rng: nextRng };
    }
    cursor -= entry.weight;
  }

  return { value: validEntries[validEntries.length - 1]!.value, rng: nextRng };
}
