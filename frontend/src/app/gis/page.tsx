"use client";

import { useEffect, useState } from "react";
import { LayerControl } from "@/components/LayerControl";
import { MapPanel } from "@/components/MapPanel";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import type { Facility, ThermalEvent } from "@/types/domain";

export default function GisExplorerPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [showEvents, setShowEvents] = useState(true);
  const [showFacilities, setShowFacilities] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listEvents(), api.listFacilities()]).then(([e, f]) => {
      setEvents(e);
      setFacilities(f);
    });
  }, []);

  const visibleEvents = showEvents ? events.filter((e) => !severityFilter || e.severity === severityFilter) : [];
  const visibleFacilities = showFacilities ? facilities : [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-base-100">GIS Explorer</h1>
        <p className="text-sm text-base-400">Thermal events, industrial facilities, and their historical spatial context.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <Panel title="Layers" className="xl:col-span-1">
          <LayerControl
            layers={[
              { key: "events", label: `Thermal events (${events.length})`, enabled: showEvents, color: "#d97b3f" },
              { key: "facilities", label: `Facilities (${facilities.length})`, enabled: showFacilities, color: "#5a6169" },
            ]}
            onToggle={(key) => (key === "events" ? setShowEvents((v) => !v) : setShowFacilities((v) => !v))}
          />
          <div className="mt-4 border-t border-base-700 pt-3">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-base-400">Severity filter</div>
            <div className="flex flex-wrap gap-1.5">
              {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(severityFilter === s ? null : s)}
                  className={`rounded border px-2 py-1 text-[11px] ${severityFilter === s ? "border-accent text-accent" : "border-base-600 text-base-300"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </Panel>
        <Panel className="xl:col-span-3">
          <MapPanel events={visibleEvents} facilities={visibleFacilities} height={560} />
        </Panel>
      </div>
    </div>
  );
}
