from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.engine import create_initial_state
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.models import Event
from bit_life_survival.core.selector import _option_access_multiplier, _unlocked_option_count


def _make_event(event_id: str, options: list[dict]) -> Event:
    return Event.model_validate(
        {
            "id": event_id,
            "title": "Test Event",
            "text": "Testing accessibility weighting.",
            "tags": ["early"],
            "trigger": {"biomeIds": ["suburbs"], "minDistance": 0},
            "weight": 1.0,
            "options": options,
        }
    )


def test_option_accessibility_multiplier_prefers_more_playable_events() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    state = create_initial_state(seed=123, biome_id="suburbs")
    easy_event = _make_event(
        "easy",
        [
            {"id": "a", "label": "Safe A", "outcomes": [{"meters": {"stamina": 0}}], "logLine": "A"},
            {"id": "b", "label": "Safe B", "outcomes": [{"meters": {"hydration": 0}}], "logLine": "B"},
            {"id": "c", "label": "Safe C", "outcomes": [{"meters": {"morale": 0}}], "logLine": "C"},
        ],
    )
    gated_event = _make_event(
        "gated",
        [
            {"id": "a", "label": "Open", "outcomes": [{"meters": {"stamina": 0}}], "logLine": "A"},
            {
                "id": "b",
                "label": "Locked B",
                "requirements": {"hasTag": "Medical"},
                "outcomes": [{"meters": {"hydration": 0}}],
                "logLine": "B",
            },
            {
                "id": "c",
                "label": "Locked C",
                "requirements": {"hasTag": "Authority"},
                "outcomes": [{"meters": {"morale": 0}}],
                "logLine": "C",
            },
        ],
    )

    easy_mult = _option_access_multiplier(easy_event, state, content)
    gated_mult = _option_access_multiplier(gated_event, state, content)
    assert easy_mult > gated_mult


def test_unlocked_option_count_reports_playable_options() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    state = create_initial_state(seed=999, biome_id="suburbs")
    event = _make_event(
        "mix",
        [
            {"id": "a", "label": "Open", "outcomes": [{"meters": {"stamina": 0}}], "logLine": "A"},
            {
                "id": "b",
                "label": "Locked",
                "requirements": {"hasTag": "Medical"},
                "outcomes": [{"meters": {"hydration": 0}}],
                "logLine": "B",
            },
            {"id": "c", "label": "Open 2", "outcomes": [{"meters": {"morale": 0}}], "logLine": "C"},
        ],
    )
    assert _unlocked_option_count(event, state, content) == 2
