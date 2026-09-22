"use client";

import { useEffect, useState } from "react";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import type { ThermalEvent } from "@/types/domain";

export default function ReportsPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [selected, setSelected] = useState("");
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e.length) setSelected(e[0].event_id);
    });
  }, []);

  async function generate() {
    if (!selected) return;
    setBusy(true);
    try {
      const r = await api.generateEventReport(selected);
      setReport(r);
    } finally {
      setBusy(false);
    }
  }

  function downloadReportJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orbiflare_incident_report_${selected}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Reports</h1>
        <p className="text-sm text-base-400">Export event data and generate full traceable incident reports.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Bulk exports">
          <div className="flex flex-col gap-2">
            <a href={api.eventsCsvUrl()} className="rounded border border-base-600 px-3 py-2 text-center text-sm text-base-200 hover:border-accent/50 hover:text-accent">
              Download all events -- CSV
            </a>
            <a href={api.eventsGeojsonUrl()} className="rounded border border-base-600 px-3 py-2 text-center text-sm text-base-200 hover:border-accent/50 hover:text-accent">
              Download all events -- GeoJSON
            </a>
          </div>
        </Panel>

        <Panel title="Incident report">
          <div className="flex gap-2">
            <select value={selected} onChange={(e) => setSelected(e.target.value)} className="flex-1 rounded border border-base-600 bg-base-800 px-2 py-2 text-sm text-base-100">
              {events.map((e) => (
                <option key={e.event_id} value={e.event_id}>
                  {e.event_id} -- {e.severity || "unscored"}
                </option>
              ))}
            </select>
            <button onClick={generate} disabled={busy} className="rounded bg-accent px-4 py-2 text-sm font-medium text-base-950 disabled:opacity-50">
              Generate
            </button>
          </div>
          {report && (
            <div className="mt-3">
              <button onClick={downloadReportJson} className="text-xs font-medium text-accent hover:underline">
                Download full report (JSON) &darr;
              </button>
              <pre className="mt-2 max-h-72 overflow-auto rounded border border-base-700 bg-base-900 p-3 text-[10px] leading-relaxed text-base-300 scrollbar-thin">
                {JSON.stringify(report, null, 2)}
              </pre>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
