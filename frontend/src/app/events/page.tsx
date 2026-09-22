"use client";

import { useEffect, useMemo, useState } from "react";
import { EventCard } from "@/components/EventCard";
import { FilterBar, FilterSelect } from "@/components/FilterBar";
import { api } from "@/lib/api";
import type { ThermalEvent } from "@/types/domain";

type SortKey = "risk" | "recency" | "persistence" | "deviation";

export default function EventsPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [trajectory, setTrajectory] = useState("");
  const [classification, setClassification] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("risk");

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      setLoading(false);
    });
  }, []);

  const filtered = useMemo(() => {
    let list = events;
    if (severity) list = list.filter((e) => e.severity === severity);
    if (status) list = list.filter((e) => e.status === status);
    if (trajectory) list = list.filter((e) => e.trajectory_direction === trajectory);
    if (classification) list = list.filter((e) => e.classification === classification);

    const sorted = [...list];
    if (sortKey === "risk") sorted.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    if (sortKey === "recency") sorted.sort((a, b) => new Date(b.first_detected).getTime() - new Date(a.first_detected).getTime());
    if (sortKey === "persistence") sorted.sort((a, b) => b.observation_count - a.observation_count);
    if (sortKey === "deviation") sorted.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    return sorted;
  }, [events, severity, status, trajectory, classification, sortKey]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Events</h1>
        <p className="text-sm text-base-400">{filtered.length} of {events.length} thermal event(s)</p>
      </div>

      <FilterBar>
        <FilterSelect label="Severity" value={severity} onChange={setSeverity} options={[
          { label: "Critical", value: "CRITICAL" }, { label: "High", value: "HIGH" }, { label: "Medium", value: "MEDIUM" }, { label: "Low", value: "LOW" },
        ]} />
        <FilterSelect label="Status" value={status} onChange={setStatus} options={[
          "DETECTED", "VALIDATING", "ALERTED", "ESCALATED", "MONITORING", "EXTINGUISHED",
        ].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Trajectory" value={trajectory} onChange={setTrajectory} options={[
          "ESCALATING", "INCREASING", "STABLE", "DECREASING", "INSUFFICIENT_DATA",
        ].map((s) => ({ label: s, value: s }))} />
        <FilterSelect label="Classification" value={classification} onChange={setClassification} options={[
          { label: "Persistent Industrial", value: "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE" },
          { label: "Natural/Agricultural Candidate", value: "NATURAL_AGRICULTURAL_FIRE_CANDIDATE" },
        ]} />
        <label className="ml-auto flex items-center gap-1.5 text-xs text-base-300">
          Sort by
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)} className="rounded border border-base-600 bg-base-800 px-2 py-1 text-xs text-base-100">
            <option value="risk">Risk</option>
            <option value="recency">Recency</option>
            <option value="persistence">Persistence</option>
          </select>
        </label>
      </FilterBar>

      {loading ? (
        <p className="text-sm text-base-400">Loading events...</p>
      ) : (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((e) => (
            <EventCard key={e.event_id} event={e} />
          ))}
        </div>
      )}
    </div>
  );
}
