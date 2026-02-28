from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.engine import create_initial_state, run_simulation
from bit_life_survival.core.loader import load_content


def _snapshot_state(state):
    return {
        "seed": state.seed,
        "step": state.step,
        "distance": round(state.distance, 6),
        "time": state.time,
        "meters": (
            round(state.meters.stamina, 6),
            round(state.meters.hydration, 6),
            round(state.meters.morale, 6),
        ),
        "injury": round(state.injury, 6),
        "flags": sorted(state.flags),
        "inventory": sorted(state.inventory.items()),
        "dead": state.dead,
        "death_reason": state.death_reason,
        "last_event_id": state.last_event_id,
        "recent_event_ids": list(state.recent_event_ids),
        "cooldowns": sorted(state.event_cooldowns.items()),
        "rng": (state.rng_state, state.rng_calls),
    }


def test_same_seed_and_policy_produce_identical_results():
    content = load_content(Path(__file__).resolve().parents[1] / "content")

    state_a = create_initial_state(777, "suburbs")
    final_a, log_a = run_simulation(state_a, content, steps=25, policy="safe")

    state_b = create_initial_state(777, "suburbs")
    final_b, log_b = run_simulation(state_b, content, steps=25, policy="safe")

    assert _snapshot_state(final_a) == _snapshot_state(final_b)
    assert [entry.format() for entry in log_a] == [entry.format() for entry in log_b]
