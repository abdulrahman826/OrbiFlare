import type { BaselineConfidence, Severity, TrajectoryDirection } from "@/types/domain";

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "--";
  return v.toFixed(digits);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function fmtRelative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  LOW: "text-sev-low border-sev-low/40 bg-sev-low/10",
  MEDIUM: "text-sev-medium border-sev-medium/40 bg-sev-medium/10",
  HIGH: "text-sev-high border-sev-high/40 bg-sev-high/10",
  CRITICAL: "text-sev-critical border-sev-critical/40 bg-sev-critical/10",
};

export const TRAJECTORY_LABEL: Record<TrajectoryDirection, string> = {
  STABLE: "Stable",
  INCREASING: "Increasing",
  ESCALATING: "Escalating",
  DECREASING: "Decreasing",
  INSUFFICIENT_DATA: "Insufficient data",
};

export const TRAJECTORY_COLORS: Record<TrajectoryDirection, string> = {
  STABLE: "text-base-200 border-base-500/50 bg-base-700/40",
  INCREASING: "text-sev-medium border-sev-medium/40 bg-sev-medium/10",
  ESCALATING: "text-sev-critical border-sev-critical/40 bg-sev-critical/10",
  DECREASING: "text-accent border-accent/40 bg-accent/10",
  INSUFFICIENT_DATA: "text-base-300 border-base-500/40 bg-base-700/30",
};

export const BASELINE_COLORS: Record<BaselineConfidence, string> = {
  ESTABLISHED: "text-sev-low border-sev-low/40 bg-sev-low/10",
  LIMITED: "text-sev-medium border-sev-medium/40 bg-sev-medium/10",
  INSUFFICIENT: "text-sev-critical border-sev-critical/40 bg-sev-critical/10",
};

export function facilityTypeLabel(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function classificationLabel(c: string | null): string {
  if (!c) return "Unclassified";
  if (c === "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE") return "Persistent Industrial Source";
  if (c === "NATURAL_AGRICULTURAL_FIRE_CANDIDATE") return "Natural/Agricultural Candidate";
  return c;
}
