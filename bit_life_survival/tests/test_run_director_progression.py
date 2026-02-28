from __future__ import annotations

from bit_life_survival.core.run_director import profile_for_seed, snapshot, steps_until_next_wave


def test_run_director_threat_and_reward_scale_with_distance() -> None:
    early = snapshot(0.0, 0)
    mid = snapshot(18.0, 18)
    late = snapshot(40.0, 40)
    assert early.threat_tier < mid.threat_tier <= late.threat_tier
    assert early.reward_multiplier < mid.reward_multiplier < late.reward_multiplier
    assert early.drain_multiplier < late.drain_multiplier


def test_run_director_wave_pattern_is_deterministic() -> None:
    values_a = [snapshot(12.0, step).wave_strength for step in range(1, 16)]
    values_b = [snapshot(12.0, step).wave_strength for step in range(1, 16)]
    assert values_a == values_b


def test_run_director_wave_has_early_grace_then_pulses() -> None:
    early = [snapshot(6.0, step).wave_strength for step in range(1, 6)]
    later = [snapshot(6.0, step).wave_strength for step in range(6, 18)]
    assert all(value == 0.0 for value in early)
    assert any(value > 0.0 for value in later)


def test_steps_until_next_wave_counts_down_and_resets_after_pulse() -> None:
    assert steps_until_next_wave(1) >= 1
    assert steps_until_next_wave(5) == 1
    assert steps_until_next_wave(6) == 3
    assert steps_until_next_wave(8) == 1
    assert steps_until_next_wave(9) == 0


def test_run_profile_is_deterministic_for_seed_and_changes_scaling() -> None:
    profile_a = profile_for_seed(12345)
    profile_b = profile_for_seed(12345)
    assert profile_a == profile_b
    baseline = snapshot(20.0, 20)
    seeded = snapshot(20.0, 20, 12345)
    assert seeded.profile_id == profile_a.id
    assert seeded.reward_multiplier > 0.0
    assert baseline.reward_multiplier > 0.0
