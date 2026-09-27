// Map display focus. PURE presentation helpers: they filter and rank what is DRAWN. They never change an event, its classification, its risk,
// the event counts shown elsewhere, alerts, analytics or the database. "Actionable" is a display predicate over already-stored fields.
import { interpretationOf } from "@/lib/interpretation";
import type { ThermalEvent } from "@/types/domain";

export type MapFocus = "ACTIONABLE" | "ALL" | "UNCERTAIN";
export const DEFAULT_MAP_FOCUS: MapFocus = "ACTIONABLE";
export const MAP_FOCUS_ORDER: MapFocus[] = ["ACTIONABLE", "ALL", "UNCERTAIN"];
export const MAP_FOCUS_LABEL: Record<MapFocus, string> = { ACTIONABLE: "Actionable", ALL: "All events", UNCERTAIN: "Uncertain" };

type E = Pick<ThermalEvent, "source_interpretation" | "severity" | "observation_count" | "baseline_confidence" | "overall_deviation_score">;

export const isUncertain = (e: E): boolean => interpretationOf(e).cls === "UNCERTAIN";
const isPriority = (e: E) => e.severity === "HIGH" || e.severity === "CRITICAL";

/** Worth foregrounding on the map: any interpreted candidate, any MEDIUM/HIGH/CRITICAL event, or an otherwise-uncertain event with meaningful evidence
 *  (several detections, or a notable deviation from an established/limited facility baseline). */
export function isActionable(e: E): boolean {
  if (!isUncertain(e)) return true;
  if (isPriority(e) || e.severity === "MEDIUM") return true;
  if ((e.observation_count ?? 0) >= 4) return true;
  return (e.baseline_confidence === "ESTABLISHED" || e.baseline_confidence === "LIMITED") && (e.overall_deviation_score ?? 0) >= 50;
}

/** New array; the input events are never mutated. */
export function eventsForFocus<T extends E>(events: readonly T[], focus: MapFocus): T[] {
  if (focus === "ALL") return [...events];
  if (focus === "UNCERTAIN") return events.filter(isUncertain);
  return events.filter(isActionable);
}

/** Which event represents a crowded screen cell (higher wins): HIGH/CRITICAL > MEDIUM > interpreted (moderate+ evidence) > interpreted (low evidence) > uncertain.
 *  An uncertain HIGH/MEDIUM event keeps its priority rank, so it is never crowded out by interpreted LOW events. */
export function displayPriority(e: E): number {
  if (isPriority(e)) return 50;
  if (e.severity === "MEDIUM") return 40;
  const i = interpretationOf(e);
  if (i.cls === "UNCERTAIN") return 10;
  return i.strength === "HIGH" || i.strength === "MODERATE" ? 30 : 20;
}
