from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True, slots=True)
class RunProfile:
    id: str
    name: str
    blurb: str
    drain_mul: float
    hazard_mul: float
    reward_mul: float
    wave_mul: float


@dataclass(frozen=True, slots=True)
class DirectorSnapshot:
    threat_tier: int
    drain_multiplier: float
    hazard_multiplier: float
    reward_multiplier: float
    wave_active: bool
    wave_strength: float
    profile_id: str
    profile_name: str
    profile_blurb: str


TIER_TABLE: tuple[tuple[float, float, float, float], ...] = (
    (10.0, 0.82, 0.84, 0.90),
    (18.0, 0.94, 0.95, 1.00),
    (28.0, 1.08, 1.14, 1.20),
    (40.0, 1.26, 1.34, 1.45),
    (9999.0, 1.45, 1.56, 1.82),
)

EXTRACTION_MILESTONES: tuple[float, ...] = (12.0, 22.0, 35.0)
WAVE_CYCLE = 9
WAVE_GRACE_STEPS = 6

RUN_PROFILES: tuple[RunProfile, ...] = (
    RunProfile(
        id="balanced",
        name="Balanced Sweep",
        blurb="Steady pacing with predictable pressure.",
        drain_mul=1.00,
        hazard_mul=1.00,
        reward_mul=1.00,
        wave_mul=1.00,
    ),
    RunProfile(
        id="parched",
        name="Parched Front",
        blurb="Harsher resource drain, stronger long-run payout.",
        drain_mul=1.12,
        hazard_mul=1.04,
        reward_mul=1.10,
        wave_mul=1.08,
    ),
    RunProfile(
        id="salvage",
        name="Salvage Window",
        blurb="Loot-rich lanes with elevated combat risk.",
        drain_mul=1.02,
        hazard_mul=1.12,
        reward_mul=1.18,
        wave_mul=1.05,
    ),
    RunProfile(
        id="fortified",
        name="Fortified Route",
        blurb="Softer start profile with safer extraction rhythm.",
        drain_mul=0.92,
        hazard_mul=0.90,
        reward_mul=0.92,
        wave_mul=0.85,
    ),
)


def _tier_for_distance(distance: float) -> int:
    for idx, (limit, _, _, _) in enumerate(TIER_TABLE):
        if distance < limit:
            return idx
    return len(TIER_TABLE) - 1


def _wave_strength(step: int) -> float:
    if step <= 0 or step < WAVE_GRACE_STEPS:
        return 0.0
    phase = step % WAVE_CYCLE
    if phase in {0, 1}:
        return 0.20
    if phase == 2:
        return 0.11
    if phase == 3:
        return 0.05
    return 0.0


def _seed_to_int(seed: int | str | None) -> int:
    if seed is None:
        return 0
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def profile_for_seed(seed: int | str | None) -> RunProfile:
    if not RUN_PROFILES:
        raise RuntimeError("Run profiles are not configured.")
    idx = _seed_to_int(seed) % len(RUN_PROFILES)
    return RUN_PROFILES[idx]


def steps_until_next_wave(step: int) -> int:
    if step < WAVE_GRACE_STEPS:
        return max(1, WAVE_GRACE_STEPS - step)
    for ahead in range(0, WAVE_CYCLE + 1):
        if _wave_strength(step + ahead) > 0.0:
            return ahead
    return WAVE_CYCLE


def snapshot(distance: float, step: int, seed: int | str | None = None) -> DirectorSnapshot:
    tier = _tier_for_distance(distance)
    _, drain, hazard, reward = TIER_TABLE[tier]
    profile = profile_for_seed(seed)
    drain *= profile.drain_mul
    hazard *= profile.hazard_mul
    reward *= profile.reward_mul

    wave = _wave_strength(step) * profile.wave_mul
    if wave > 0.0:
        drain *= 1.0 + wave
        hazard *= 1.0 + (wave * 0.5)
        reward *= 1.0 + (wave * 0.8)
    return DirectorSnapshot(
        threat_tier=tier,
        drain_multiplier=drain,
        hazard_multiplier=hazard,
        reward_multiplier=reward,
        wave_active=wave > 0.0,
        wave_strength=wave,
        profile_id=profile.id,
        profile_name=profile.name,
        profile_blurb=profile.blurb,
    )


def next_extraction_target(distance: float) -> float:
    for target in EXTRACTION_MILESTONES:
        if distance < target:
            return target
    return EXTRACTION_MILESTONES[-1]


def reached_extraction_target(distance: float) -> float | None:
    reached = None
    for target in EXTRACTION_MILESTONES:
        if distance >= target:
            reached = target
        else:
            break
    return reached


def can_extract(distance: float, step: int, seed: int | str | None = None) -> bool:
    if reached_extraction_target(distance) is None:
        return False
    return not snapshot(distance, step, seed).wave_active
