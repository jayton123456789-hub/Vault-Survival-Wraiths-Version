from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


def seed_to_uint32(seed: int | str) -> int:
    text = str(seed).encode("utf-8")
    digest = hashlib.sha256(text).hexdigest()
    value = int(digest[:8], 16)
    return value if value != 0 else 0x9E3779B9


@dataclass(slots=True)
class WeightedEntry(Generic[T]):
    value: T
    weight: float


@dataclass(slots=True)
class DeterministicRNG:
    seed: int | str
    state: int
    calls: int = 0

    @classmethod
    def from_seed(cls, seed: int | str) -> "DeterministicRNG":
        return cls(seed=seed, state=seed_to_uint32(seed), calls=0)

    def _next_uint32(self) -> int:
        value = self.state & 0xFFFFFFFF
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= (value >> 17) & 0xFFFFFFFF
        value ^= (value << 5) & 0xFFFFFFFF
        value &= 0xFFFFFFFF
        self.state = value if value != 0 else 0x6D2B79F5
        self.calls += 1
        return self.state

    def next_float(self) -> float:
        return self._next_uint32() / 2**32

    def next_int(self, min_inclusive: int, max_exclusive: int) -> int:
        if max_exclusive <= min_inclusive:
            raise ValueError(
                f"next_int requires max_exclusive ({max_exclusive}) > min_inclusive ({min_inclusive})."
            )
        span = max_exclusive - min_inclusive
        return min_inclusive + int(self.next_float() * span)

    def pick_weighted(self, entries: Sequence[WeightedEntry[T]]) -> T:
        valid_entries = [entry for entry in entries if entry.weight > 0]
        if not valid_entries:
            raise ValueError("pick_weighted requires at least one positive weight.")

        total_weight = sum(entry.weight for entry in valid_entries)
        cursor = self.next_float() * total_weight
        for entry in valid_entries:
            if cursor < entry.weight:
                return entry.value
            cursor -= entry.weight
        return valid_entries[-1].value
