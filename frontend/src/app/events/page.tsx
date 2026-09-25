"use client";

import { useEffect, useMemo, useState } from "react";
import { EventTable } from "@/components/EventTable";
import { FilterBar, FilterSelect } from "@/components/FilterBar";
import { MapPanel } from "@/components/MapPanel";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";
import { facilityTypeLabel } from "@/lib/format";
import type { Facility, ThermalEvent } from "@/types/domain";

type SortKey = "risk" | "recency" | "persistence" | "deviation";

const WINDOWS: Record<string, number> = { "24h": 24, "7d": 168, "30d": 720 };

export default function EventsPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [f, setF] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState<SortKey>("risk");
  const set = (k: string) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    Promise.all([api.listEvents(), api.listFacilities()])
      .then(([e, fac]) => { setEvents(e); setFacilities(fac); })
      .catch((err) => setError(String(err?.message ?? err)))
      .finally(() => setLoading(false));
  }, []);

  const names = useMemo(() => Object.fromEntries(facilities.map((x) => [x.facility_id, x.name])), [facilities]);
  const facilityTypeOptions = useMemo(
    () => Array.from(new Set(events.map((e) => e.facility_type).filter((t): t is string => !!t))).sort(),
    [events]
  );

  const filtered = useMemo(() => {
    // The time window is anchored to the newest observation in the data set, not wall-clock,
    // so it behaves the same for a fixed demo snapshot and for live data.
    const anchor = events.reduce((m, e) => Math.max(m, new Date(e.last_detected).getTime()), 0);
    let list = events.filter((e) =>
      (!f.severity || e.severity === f.severity) &&
      (!f.status || e.status === f.status) &&
      (!f.trajectory || e.trajectory_direction === f.trajectory) &&
      (!f.classification || e.classification === f.classification) &&
      (!f.facilityType || e.facility_type === f.facilityType) &&
      (!f.baseline || e.baseline_confidence === f.baseline) &&
      (!f.provenance || (f.provenance === "DEMO" ? e.is_demo : !e.is_demo)) &&
      (!f.window || anchor - new Date(e.last_detected).getTime() <= WINDOWS[f.window] * 3600_000)
    );
    list = [...list];
    if (sortKey === "risk") list.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    if (sortKey === "recency") list.sort((a, b) => new Date(b.last_detected).getTime() - new Date(a.last_detected).getTime());
    if (sortKey === "persistence") list.sort((a, b) => b.observation_count - a.observation_count);
    if (sortKey === "deviation") list.sort((a, b) => (b.overall_deviation_score ?? -1) - (a.overall_deviation_score ?? -1));
    return list;
  }, [events, f, sortKey]);

  const activeFilters = Object.values(f).filter(Boolean).length;

  return (
    <div className="space-y-3">
      <PageHeader
        title="Events"
        sub={`${filtered.length} of ${events.length} living thermal events. An event is an evolving cluster of observations, not a single hotspot.`}
        action={
          <button onClick={() => setShowMap((v) => !v)} aria-pressed={showMap} className="btn-secondary">
            {showMap ? "Hide map" : "Show map"}
          </button>
        }
      />

      <FilterBar>
        <FilterSelect label="Severity" value={f.severity ?? ""} onChange={set("severity")} options={["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Status" value={f.status ?? ""} onChange={set("status")} options={["DETECTED", "VALIDATING", "ALERTED", "ESCALATED", "MONITORING", "EXTINGUISHED"].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Trajectory" value={f.trajectory ?? ""} onChange={set("trajectory")} options={["ESCALATING", "INCREASING", "STABLE", "DECREASING", "INSUFFICIENT_DATA"].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Class" value={f.classification ?? ""} onChange={set("classification")} options={[
          { label: "Persistent industrial", value: "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE" },
          { label: "Natural/agri candidate", value: "NATURAL_AGRICULTURAL_FIRE_CANDIDATE" },
        ]} />
        <FilterSelect label="Facility type" value={f.facilityType ?? ""} onChange={set("facilityType")} options={facilityTypeOptions.map((t) => ({ label: facilityTypeLabel(t), value: t }))} />
        <FilterSelect label="Baseline" value={f.baseline ?? ""} onChange={set("baseline")} options={["ESTABLISHED", "LIMITED", "INSUFFICIENT"].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Source" value={f.provenance ?? ""} onChange={set("provenance")} options={[{ label: "Demo", value: "DEMO" }, { label: "Live / FIRMS", value: "LIVE" }]} />
        <FilterSelect label="Window" value={f.window ?? ""} onChange={set("window")} options={[{ label: "Last 24h", value: "24h" }, { label: "Last 7d", value: "7d" }, { label: "Last 30d", value: "30d" }]} />
        <label className="ml-auto flex items-center gap-1.5 text-xs text-base-300">
          Sort
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)} className="rounded border border-base-600 bg-base-800 px-2 py-1 text-xs text-base-100 focus:border-accent focus:outline-none">
            <option value="risk">Risk</option>
            <option value="recency">Recency</option>
            <option value="persistence">Persistence</option>
            <option value="deviation">Deviation</option>
          </select>
        </label>
        {activeFilters > 0 && (
          <button onClick={() => setF({})} className="text-xs font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Reset ({activeFilters})</button>
        )}
      </FilterBar>

      {showMap && (
        <Panel title="Filtered events on map" flush>
          <div className="p-2"><MapPanel events={filtered} facilities={facilities} height={340} /></div>
        </Panel>
      )}

      {error ? (
        <StateBlock kind="error" title="Could not load events">{error}</StateBlock>
      ) : loading ? (
        <StateBlock kind="empty" title="Loading events…" />
      ) : filtered.length === 0 ? (
        <StateBlock kind="empty" title="No events match the current filters">
          {events.length === 0 ? "The pipeline has produced no events yet." : "Adjust or reset the filters."}
        </StateBlock>
      ) : (
        <Panel flush><EventTable events={filtered} facilityNames={names} /></Panel>
      )}
    </div>
  );
}
