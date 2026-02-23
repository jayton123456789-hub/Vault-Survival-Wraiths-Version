import { LoadedContent } from "../content/loader";
import { RequirementExpr } from "../content/schemas";
import { RunnerState, ownedItemIds, ownsItem } from "./state";

export interface RequirementCheck {
  readonly ok: boolean;
  readonly reasons: string[];
}

function evaluateLeaf(
  requirement: RequirementExpr,
  state: RunnerState,
  content: LoadedContent
): RequirementCheck {
  if ("hasTag" in requirement) {
    const ownedIds = ownedItemIds(state);
    const hasTag = ownedIds.some((itemId) => content.itemById[itemId]?.tags.includes(requirement.hasTag));
    return hasTag
      ? { ok: true, reasons: [] }
      : { ok: false, reasons: [`Requires an owned item tagged '${requirement.hasTag}'.`] };
  }
  if ("hasItem" in requirement) {
    const hasItem = ownsItem(state, requirement.hasItem);
    return hasItem
      ? { ok: true, reasons: [] }
      : { ok: false, reasons: [`Requires item '${requirement.hasItem}' in inventory or equipped.`] };
  }
  if ("flag" in requirement) {
    const hasFlag = state.flags.has(requirement.flag);
    return hasFlag ? { ok: true, reasons: [] } : { ok: false, reasons: [`Requires flag '${requirement.flag}'.`] };
  }
  if ("meterGte" in requirement) {
    const currentValue = state.meters[requirement.meterGte.meter];
    return currentValue >= requirement.meterGte.value
      ? { ok: true, reasons: [] }
      : {
          ok: false,
          reasons: [`Requires ${requirement.meterGte.meter} >= ${requirement.meterGte.value}.`]
        };
  }
  if ("injuryLte" in requirement) {
    return state.injury <= requirement.injuryLte
      ? { ok: true, reasons: [] }
      : { ok: false, reasons: [`Requires injury <= ${requirement.injuryLte}.`] };
  }
  if ("distanceGte" in requirement) {
    return state.distance >= requirement.distanceGte
      ? { ok: true, reasons: [] }
      : { ok: false, reasons: [`Requires distance >= ${requirement.distanceGte}.`] };
  }
  return { ok: false, reasons: ["Unknown requirement."] };
}

export function evaluateRequirement(
  requirement: RequirementExpr,
  state: RunnerState,
  content: LoadedContent
): RequirementCheck {
  if ("all" in requirement) {
    const checks = requirement.all.map((expr) => evaluateRequirement(expr, state, content));
    const failed = checks.filter((check) => !check.ok);
    return failed.length === 0
      ? { ok: true, reasons: [] }
      : { ok: false, reasons: failed.flatMap((check) => check.reasons) };
  }

  if ("any" in requirement) {
    const checks = requirement.any.map((expr) => evaluateRequirement(expr, state, content));
    if (checks.some((check) => check.ok)) {
      return { ok: true, reasons: [] };
    }
    const leafReasons = checks.flatMap((check) => check.reasons);
    return {
      ok: false,
      reasons: [
        leafReasons.length > 0
          ? `Requires any of: ${leafReasons.join(" OR ")}`
          : "Requires any of the listed requirements."
      ]
    };
  }

  if ("not" in requirement) {
    const check = evaluateRequirement(requirement.not, state, content);
    return check.ok
      ? { ok: false, reasons: ["Disallowed condition is currently true."] }
      : { ok: true, reasons: [] };
  }

  return evaluateLeaf(requirement, state, content);
}
