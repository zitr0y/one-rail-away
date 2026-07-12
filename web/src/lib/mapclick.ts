// Routes a map station click to a selection action based on which planner
// field is "armed". Pure, unit-testable. Spec: 2026-07-12-unified-planner-panel.
import type { FeaturePick } from "./pickfeature";

export type ActiveField = "from" | "to" | null;

/**
 * Which field the next map station click should fill. An explicitly focused
 * field wins; otherwise default to "to" when an origin exists, else "from".
 */
export function armedTarget(activeField: ActiveField, hasOrigin: boolean): "from" | "to" {
  return activeField ?? (hasOrigin ? "to" : "from");
}

export type MapClickAction =
  | { action: "origin"; id: string }
  | { action: "dest"; id: string }
  | { action: "unreachableTo"; id: string };

/**
 * Route a station click given the armed target. From wins even over a
 * reachable-dot hit; To accepts only reachable dots (pick.type === "dest").
 */
export function routeMapClick(pick: FeaturePick, target: "from" | "to"): MapClickAction {
  if (target === "from") return { action: "origin", id: pick.id };
  if (pick.type === "dest") return { action: "dest", id: pick.id };
  return { action: "unreachableTo", id: pick.id };
}
