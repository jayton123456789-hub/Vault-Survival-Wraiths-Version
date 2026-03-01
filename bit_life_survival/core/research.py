from __future__ import annotations

from dataclasses import dataclass

from .models import VaultState

MAX_RESEARCH_LEVEL = 5
CAMPAIGN_TAV_TARGET = 420


@dataclass(frozen=True, slots=True)
class ResearchNode:
    id: str
    name: str
    branch: str
    description: str
    base_cost: int
    max_level: int = MAX_RESEARCH_LEVEL
    requires: tuple[str, ...] = ()


RESEARCH_NODES: tuple[ResearchNode, ...] = (
    ResearchNode("rationing", "Rationing", "Survival", "Slows hunger drain and stabilizes long pushes.", 20),
    ResearchNode("water_recycling", "Water Recycling", "Survival", "Cuts hydration loss so thirst is manageable.", 30, requires=("rationing",)),
    ResearchNode("field_medicine", "Field Medicine", "Survival", "Improves injury control and med efficiency.", 40, requires=("water_recycling",)),
    ResearchNode("salvage_tools", "Salvage Tools", "Salvage/Mobility", "Improves scrap secured on every finished run.", 30),
    ResearchNode("route_caching", "Route Caching", "Salvage/Mobility", "Improves forward momentum and carry discipline.", 40, requires=("salvage_tools",)),
    ResearchNode("deep_contracts", "Field Contracts", "Salvage/Mobility", "Unlocks contract-grade missions and higher stakes.", 80, requires=("route_caching",)),
    ResearchNode("intake_protocols", "Intake Protocols", "Population/Infrastructure", "Expands intake queue without food gating.", 20),
    ResearchNode("team_doctrine", "Team Doctrine", "Population/Infrastructure", "Unlocks additional deploy-ready runner slots.", 60, requires=("intake_protocols",)),
    ResearchNode("vault_network", "Vault Network", "Population/Infrastructure", "Raises late-game throughput and stability.", 80, requires=("team_doctrine",)),
    ResearchNode("drone_recovery_suite", "Recovery Suite", "Drone Engineering", "Raises drone return rates and lowers hard loss risk.", 40),
    ResearchNode("drone_pathing", "Drone Pathing", "Drone Engineering", "Improves deep-field corpse retrieval.", 60, requires=("drone_recovery_suite",)),
    ResearchNode("signal_uplink", "Signal Uplink", "Drone Engineering", "Reduces catastrophic retrieval failures.", 80, requires=("drone_pathing",)),
    ResearchNode("ops_planning", "Ops Planning", "Command/Operations", "Adds more reliable mission pacing and better contracts.", 40),
    ResearchNode("forward_command", "Forward Command", "Command/Operations", "Improves rewards on checkpoint extractions.", 60, requires=("ops_planning",)),
    ResearchNode("command_nexus", "Command Nexus", "Command/Operations", "Final command net needed to fully stabilize the vault.", 100, requires=("forward_command", "vault_network", "signal_uplink", "field_medicine")),
)

NODE_BY_ID = {node.id: node for node in RESEARCH_NODES}


def research_level(vault: VaultState, node_id: str) -> int:
    return max(0, int(vault.research_levels.get(node_id, 0)))


def node_unlocked(vault: VaultState, node_id: str) -> bool:
    node = NODE_BY_ID[node_id]
    return all(research_level(vault, dep) > 0 for dep in node.requires)


def next_level_cost(vault: VaultState, node_id: str) -> int | None:
    node = NODE_BY_ID[node_id]
    level = research_level(vault, node_id)
    if level >= node.max_level:
        return None
    return node.base_cost + (level * 20)


def can_research(vault: VaultState, node_id: str) -> tuple[bool, str]:
    if node_id not in NODE_BY_ID:
        return False, "Unknown research node."
    node = NODE_BY_ID[node_id]
    level = research_level(vault, node_id)
    if level >= node.max_level:
        return False, "Already maxed."
    missing = [dep for dep in node.requires if research_level(vault, dep) <= 0]
    if missing:
        labels = ", ".join(NODE_BY_ID[dep].name for dep in missing)
        return False, f"Needs {labels}."
    cost = next_level_cost(vault, node_id)
    if cost is None:
        return False, "Already maxed."
    if int(vault.materials.get("scrap", 0)) < cost:
        return False, f"Need {cost} scrap."
    return True, "Ready."


def buy_research(vault: VaultState, node_id: str) -> int:
    ok, reason = can_research(vault, node_id)
    if not ok:
        raise ValueError(reason)
    cost = int(next_level_cost(vault, node_id) or 0)
    vault.materials["scrap"] = max(0, int(vault.materials.get("scrap", 0)) - cost)
    vault.research_levels[node_id] = research_level(vault, node_id) + 1
    if research_level(vault, "command_nexus") > 0:
        vault.campaign_goal_unlocked = True
    if campaign_progress(vault) >= 1.0 and int(vault.tav) >= CAMPAIGN_TAV_TARGET:
        vault.campaign_won = True
    return cost


def hunger_drain_multiplier(vault: VaultState) -> float:
    return max(0.55, 1.0 - (0.08 * research_level(vault, "rationing")))


def hydration_drain_multiplier(vault: VaultState) -> float:
    return max(0.6, 1.0 - (0.07 * research_level(vault, "water_recycling")))


def injury_relief_bonus(vault: VaultState) -> float:
    return 0.04 * research_level(vault, "field_medicine")


def salvage_scrap_bonus(vault: VaultState) -> int:
    return (2 * research_level(vault, "salvage_tools")) + (2 * research_level(vault, "route_caching"))


def travel_speed_bonus(vault: VaultState) -> float:
    return 0.02 * research_level(vault, "route_caching")


def queue_capacity_bonus(vault: VaultState) -> int:
    return research_level(vault, "intake_protocols")


def deploy_capacity(vault: VaultState) -> int:
    return 1 + research_level(vault, "team_doctrine")


def drone_recovery_bonus(vault: VaultState) -> float:
    return (0.06 * research_level(vault, "drone_recovery_suite")) + (0.03 * research_level(vault, "drone_pathing"))


def drone_failure_guard(vault: VaultState) -> float:
    return (0.03 * research_level(vault, "signal_uplink")) + (0.02 * research_level(vault, "drone_pathing"))


def extraction_reward_bonus(vault: VaultState) -> float:
    return 0.03 * research_level(vault, "forward_command")


def contracts_unlocked(vault: VaultState) -> bool:
    return research_level(vault, "deep_contracts") > 0


def contract_label(vault: VaultState) -> str:
    if not contracts_unlocked(vault):
        return "Bootstrap Salvage Sweep"
    tier = research_level(vault, "deep_contracts")
    if tier >= 4:
        return "Priority Recovery Contract"
    if tier >= 2:
        return "Regional Salvage Contract"
    return "Local Contract Sweep"


def campaign_progress(vault: VaultState) -> float:
    tracked = ("field_medicine", "route_caching", "team_doctrine", "signal_uplink", "forward_command", "command_nexus")
    total = len(tracked) * MAX_RESEARCH_LEVEL
    earned = sum(min(MAX_RESEARCH_LEVEL, research_level(vault, node_id)) for node_id in tracked)
    return 0.0 if total <= 0 else max(0.0, min(1.0, earned / total))
