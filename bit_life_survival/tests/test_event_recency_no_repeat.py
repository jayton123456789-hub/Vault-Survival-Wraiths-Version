from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.engine import advance_to_next_event, create_initial_state
from bit_life_survival.core.loader import load_content


def test_event_selection_avoids_recent_repeat_window_when_pool_is_available() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    state = create_initial_state(4242, "suburbs")
    event_ids: list[str] = []
    for _ in range(22):
        state, event_instance, _ = advance_to_next_event(state, content)
        state.meters.stamina = 100.0
        state.meters.hydration = 100.0
        state.meters.morale = 100.0
        state.injury = 0.0
        state.dead = False
        state.death_reason = None
        if event_instance is None:
            continue
        event_ids.append(event_instance.event_id)
    assert len(event_ids) >= 8
    for idx, event_id in enumerate(event_ids):
        recent = event_ids[max(0, idx - 5) : idx]
        assert event_id not in recent
