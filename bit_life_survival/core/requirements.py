from __future__ import annotations

from typing import Any

from .loader import ContentBundle
from .models import GameState, has_owned_item, owned_item_ids


def _check_leaf(expr: dict[str, Any], state: GameState, content: ContentBundle) -> tuple[bool, list[str]]:
    if "hasTag" in expr:
        required_tag = expr["hasTag"]
        owned_ids = owned_item_ids(state)
        has_tag = any(required_tag in content.item_by_id[item_id].tags for item_id in owned_ids if item_id in content.item_by_id)
        if has_tag:
            return True, []
        return False, [f"Requires owned item with tag '{required_tag}'."]

    if "hasItem" in expr:
        item_id = expr["hasItem"]
        has_item = has_owned_item(state, item_id)
        return (True, []) if has_item else (False, [f"Requires item '{item_id}' in inventory or equipped slots."])

    if "flag" in expr:
        flag = expr["flag"]
        has_flag = flag in state.flags
        return (True, []) if has_flag else (False, [f"Requires flag '{flag}'."])

    if "meterGte" in expr:
        payload = expr["meterGte"]
        meter = payload["meter"]
        required_value = float(payload["value"])
        current = getattr(state.meters, meter)
        if current >= required_value:
            return True, []
        return False, [f"Requires {meter} >= {required_value}."]

    if "injuryLte" in expr:
        required_injury = float(expr["injuryLte"])
        if state.injury <= required_injury:
            return True, []
        return False, [f"Requires injury <= {required_injury}."]

    if "distanceGte" in expr:
        required_distance = float(expr["distanceGte"])
        if state.distance >= required_distance:
            return True, []
        return False, [f"Requires distance >= {required_distance}."]

    return False, ["Unknown requirement."]


def evaluate_requirement(expr: dict[str, Any], state: GameState, content: ContentBundle) -> tuple[bool, list[str]]:
    if "all" in expr:
        all_reasons: list[str] = []
        for child in expr["all"]:
            ok, reasons = evaluate_requirement(child, state, content)
            if not ok:
                all_reasons.extend(reasons)
        return (len(all_reasons) == 0, all_reasons)

    if "any" in expr:
        all_failures: list[str] = []
        for child in expr["any"]:
            ok, reasons = evaluate_requirement(child, state, content)
            if ok:
                return True, []
            all_failures.extend(reasons)
        if all_failures:
            return False, [f"Requires any of: {' OR '.join(all_failures)}"]
        return False, ["Requires any listed condition."]

    if "not" in expr:
        ok, _ = evaluate_requirement(expr["not"], state, content)
        if ok:
            return False, ["Blocked by negated requirement."]
        return True, []

    return _check_leaf(expr, state, content)
