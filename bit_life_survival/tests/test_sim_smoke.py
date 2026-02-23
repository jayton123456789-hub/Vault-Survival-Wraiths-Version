from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.engine import create_initial_state, run_simulation
from bit_life_survival.core.loader import load_content


def test_smoke_run_thirty_steps_without_crash():
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    initial = create_initial_state(9991, "suburbs")
    final_state, timeline = run_simulation(initial, content, steps=30, policy="safe")

    assert final_state.step > 0
    assert len(timeline) > 0
