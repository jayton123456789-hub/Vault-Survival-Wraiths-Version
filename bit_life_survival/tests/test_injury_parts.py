from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.engine import EventInstance, EventOptionInstance, apply_choice_with_state_rng_detailed, create_initial_state
from bit_life_survival.core.loader import load_content


def _injury_event() -> EventInstance:
    return EventInstance(
        event_id="injury_test",
        title="Injury Test",
        text="Deterministic injury part selection",
        tags=["hazard"],
        options=[
            EventOptionInstance(
                id="take_hit",
                label="Take the hit",
                locked=False,
                lock_reasons=[],
                requirements=None,
                costs=[],
                outcomes=[{"addInjury": 9}],
                log_line="You absorb the hit.",
                death_chance_hint=0.0,
                loot_bias=0,
            )
        ],
    )


def test_body_part_injury_assignment_is_deterministic_for_same_seed() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    event = _injury_event()

    state_a = create_initial_state(424242, "suburbs")
    state_b = create_initial_state(424242, "suburbs")
    for _ in range(4):
        apply_choice_with_state_rng_detailed(state_a, event, "take_hit", content)
        apply_choice_with_state_rng_detailed(state_b, event, "take_hit", content)

    assert state_a.injuries == state_b.injuries
    assert state_a.injury == state_b.injury
    assert any(value > 0 for value in state_a.injuries.values())
