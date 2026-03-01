from __future__ import annotations

from pathlib import Path

from bit_life_survival.core.drone import run_drone_recovery
from bit_life_survival.core.engine import create_initial_state
from bit_life_survival.core.loader import load_content
from bit_life_survival.core.persistence import (
    compute_roster_capacity,
    create_default_vault_state,
    get_active_deploy_citizen,
    on_run_finished,
    transfer_claw_pick_to_roster,
)
from bit_life_survival.core.research import buy_research, contracts_unlocked, next_level_cost
from bit_life_survival.core.travel import advance_travel


def _content():
    return load_content(Path(__file__).resolve().parents[1] / "content")


def test_research_costs_scale_and_unlock_capacity_and_contracts() -> None:
    vault = create_default_vault_state(base_seed=444)
    vault.materials["scrap"] = 600

    assert compute_roster_capacity(vault) == 1
    assert next_level_cost(vault, "salvage_tools") == 30
    buy_research(vault, "salvage_tools")
    assert next_level_cost(vault, "salvage_tools") == 50

    buy_research(vault, "intake_protocols")
    buy_research(vault, "team_doctrine")
    assert compute_roster_capacity(vault) == 2

    buy_research(vault, "route_caching")
    buy_research(vault, "deep_contracts")
    assert contracts_unlocked(vault) is True


def test_dead_runner_never_returns_as_deploy_ready() -> None:
    vault = create_default_vault_state(base_seed=555)
    picked = transfer_claw_pick_to_roster(vault, preview_count=5)
    assert get_active_deploy_citizen(vault) is not None

    on_run_finished(vault, result="death", citizen_id=picked.id)

    assert all(c.id != picked.id for c in vault.deploy_roster)
    assert any(c.id == picked.id and c.status == "dead" for c in vault.fallen_citizens)
    assert get_active_deploy_citizen(vault) is None


def test_hunger_ticks_down_and_zero_hydration_no_longer_causes_immediate_death() -> None:
    content = _content()
    state = create_initial_state(1212, "suburbs")
    state.meters.stamina = 60.0
    state.meters.hydration = 1.0
    state.hunger = 50.0

    advance_travel(state, content)

    assert state.hunger < 50.0
    assert state.meters.hydration == 0.0
    assert state.dead is False


def test_first_completed_run_scrap_recovery_lands_near_target() -> None:
    content = _content()
    vault = create_default_vault_state(base_seed=777)
    state = create_initial_state(777, "suburbs")
    state.dead = True
    state.death_reason = "Extracted successfully"
    state.death_flags.add("extracted")
    state.distance = 12.0
    state.step = 12

    report = run_drone_recovery(vault, state, content)

    assert 22 <= report.scrap_recovered <= 32
