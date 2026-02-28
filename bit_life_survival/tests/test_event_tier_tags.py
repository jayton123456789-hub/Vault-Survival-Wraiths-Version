from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.loader import load_content


def _expected_tier(min_distance: float) -> str:
    if min_distance < 6:
        return "early"
    if min_distance < 14:
        return "mid"
    if min_distance < 24:
        return "late"
    return "crisis"


def test_events_have_single_distance_tier_tag() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    tier_tags = {"early", "mid", "late", "crisis"}
    for event in content.events:
        assigned = tier_tags.intersection(event.tags)
        assert len(assigned) == 1
        min_distance = float(event.trigger.min_distance or 0.0)
        assert _expected_tier(min_distance) in assigned
