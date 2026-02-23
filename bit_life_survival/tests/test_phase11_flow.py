from __future__ import annotations

import json
from pathlib import Path

from bit_life_survival.app.screens import apply_retreat
from bit_life_survival.core.drone import run_drone_recovery
from bit_life_survival.core.engine import create_initial_state, step
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.persistence import create_default_vault_state


def _write_minimal_content(content_dir: Path) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / "items.json").write_text("[]\n", encoding="utf-8")
    (content_dir / "loottables.json").write_text("[]\n", encoding="utf-8")
    (content_dir / "biomes.json").write_text(
        json.dumps(
            [
                {
                    "id": "suburbs",
                    "name": "Test Suburbs",
                    "meterDrainMul": {"stamina": 0.2, "hydration": 0.2, "morale": 0.2},
                    "lootTableIds": [],
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (content_dir / "events.json").write_text(
        json.dumps(
            [
                {
                    "id": "event_alpha",
                    "title": "Event Alpha",
                    "text": "A",
                    "weight": 1,
                    "trigger": {"biomeIds": ["suburbs"]},
                    "options": [{"id": "ok", "label": "Ok", "outcomes": [{"metersDelta": {"morale": 0}}], "logLine": "A"}],
                },
                {
                    "id": "event_beta",
                    "title": "Event Beta",
                    "text": "B",
                    "weight": 1,
                    "trigger": {"biomeIds": ["suburbs"]},
                    "options": [{"id": "ok", "label": "Ok", "outcomes": [{"metersDelta": {"morale": 0}}], "logLine": "B"}],
                },
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_event_selection_avoids_same_event_back_to_back_when_alternatives_exist(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    _write_minimal_content(content_dir)
    content = load_content(content_dir)

    state = create_initial_state(4242, "suburbs")
    event_ids: list[str] = []

    for _ in range(12):
        _, event_instance, _ = step(state, content, policy="safe")
        if state.dead or event_instance is None:
            break
        event_ids.append(event_instance.event_id)

    assert len(event_ids) >= 4
    for prev, curr in zip(event_ids, event_ids[1:]):
        assert prev != curr


def test_retreat_path_marks_state_and_executes_drone_recovery() -> None:
    content = load_content(Path(__file__).resolve().parents[1] / "content")
    vault = create_default_vault_state(base_seed=123)
    state = create_initial_state(123, "suburbs")
    state.inventory = {"scrap": 2}
    state.equipped.pack = "backpack_basic"

    retreat_log = apply_retreat(state)
    assert state.dead is True
    assert state.death_reason == "Retreated to base"
    assert "retreated_early" in state.death_flags
    assert "penalty" in retreat_log.line.lower()

    report = run_drone_recovery(vault, state, content)
    recovered_and_lost = sum(report.recovered.values()) + sum(report.lost.values())
    assert recovered_and_lost == 3
