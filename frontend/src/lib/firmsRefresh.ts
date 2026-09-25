// Pure presentation logic for the FIRMS refresh control (kept free of React so it is unit-testable).
import type { FirmsRefreshFailure, FirmsRefreshSummary } from "@/types/domain";

export type RefreshState = "idle" | "running" | "ok" | "failed" | "unconfigured";

export interface RefreshUi {
  state: RefreshState;
  buttonLabel: string;
  buttonDisabled: boolean;
  title?: string;
  lines: string[];
}

export function idleUi(configured: boolean): RefreshUi {
  return configured
    ? { state: "idle", buttonLabel: "↻ Refresh FIRMS", buttonDisabled: false, lines: [] }
    : { state: "unconfigured", buttonLabel: "↻ Refresh FIRMS", buttonDisabled: true, title: "FIRMS NOT CONFIGURED", lines: ["Showing local / demo data"] };
}

export const RUNNING_UI: RefreshUi = { state: "running", buttonLabel: "Refreshing…", buttonDisabled: true, lines: [] };

/** Only real numbers returned by the API are shown. */
export function okUi(s: FirmsRefreshSummary): RefreshUi {
  const lines = [
    `${s.observations_received} observations received`,
    `${s.observations_stored} observations stored (${s.new_observations} new${s.updated_observations ? `, ${s.updated_observations} updated` : ""})`,
    `${s.events_created} events created · ${s.events_updated} updated · ${s.events_total} total`,
    `Source: ${s.sources.map((x) => x.product.replace(/NOAA(\d+)/, "NOAA-$1").replace(/_/g, " ")).join(" + ")}`,
  ];
  if (s.observations_received === 0) lines.push("No detections in the requested window");
  if (s.demo_data_removed.events > 0) lines.push(`Demo data removed (${s.demo_data_removed.events} events)`);
  return { state: "ok", buttonLabel: "↻ Refresh FIRMS", buttonDisabled: false, title: "FIRMS SYNC COMPLETE", lines };
}

export function failedUi(body: FirmsRefreshFailure | null): RefreshUi {
  if (body?.code === "NOT_CONFIGURED") return { ...idleUi(false), lines: ["FIRMS_MAP_KEY is not set on the server", "Showing local / demo data"] };
  return {
    state: "failed", buttonLabel: "↻ Refresh FIRMS", buttonDisabled: false, title: "FIRMS SYNC FAILED",
    lines: [body?.message ?? "The OrbiFlare API could not be reached.", "Showing last available data"],
  };
}

/** ISO (UTC, from the backend) -> "HH:MM IST". */
export function formatIst(iso: string | null | undefined): string {
  if (!iso) return "never";
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false })} IST`;
}

/** Satellite acquisition time is UTC, exactly as stored -- shown as UTC, never converted with the browser clock. */
export function formatAcquisition(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}Z` : "—";
}
