"use client";

import { useEffect, useState } from "react";
import { DemoBadge, HistoricalBadge, LiveBadge } from "@/components/DemoBadge";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";
import type { HistoricalIncident, ThermalEvent } from "@/types/domain";

const LINK = "btn-secondary py-2";

export default function ReportsPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [selected, setSelected] = useState("");
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [incidents, setIncidents] = useState<HistoricalIncident[]>([]);
  const [incidentId, setIncidentId] = useState("");
  const [incidentBusy, setIncidentBusy] = useState(false);

  useEffect(() => {
    api.listEvents()
      .then((e) => { setEvents(e); if (e.length) setSelected(e[0].event_id); })
      .catch((err) => setError(String(err?.message ?? err)));
  }, []);

  useEffect(() => {
    api.listIncidents().then((i) => { setIncidents(i); if (i.length) setIncidentId(i[0].incident_id); }).catch(() => undefined);
  }, []);

  async function generateIncident() {
    if (!incidentId) return;
    setIncidentBusy(true);
    setError(null);
    try {
      const r = await api.generateIncidentReport(incidentId);
      const url = URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `orbiflare_historical_incident_${incidentId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setIncidentBusy(false);
    }
  }

  const current = events.find((e) => e.event_id === selected);
  const demoCount = events.filter((e) => e.is_demo).length;

  async function generate() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      setReport(await api.generateEventReport(selected));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
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
    <div className="space-y-3">
      <PageHeader title="Reports" sub="Export event data and generate traceable incident reports. Exports separate observed data from derived intelligence and carry provenance." />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Panel variant="section" title="Bulk exports" sub={`${events.length} events · ${demoCount} demo`}>
          <div className="flex flex-col gap-2">
            <a href={api.eventsCsvUrl()} className={LINK}>Download all events · CSV</a>
            <a href={api.eventsGeojsonUrl()} className={LINK}>Download all events · GeoJSON</a>
          </div>
          <p className="mt-3 text-[11px] leading-snug text-base-400">
            Risk scores are operational priorities, not fire probabilities. Demo rows are sample data and are flagged in the export.
          </p>
        </Panel>

        <Panel variant="section" title="Incident report" sub="One event: observations, deviation, evidence, alternatives, risk, limitations">
          {events.length === 0 && !error ? (
            <StateBlock kind="empty" title="No events to report on" />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <select value={selected} onChange={(e) => { setSelected(e.target.value); setReport(null); }} aria-label="Event" className="min-w-[280px] flex-1 rounded border border-base-600 bg-base-800 px-2 py-2 text-sm text-base-100 focus:border-accent focus:outline-none">
                  {events.map((e) => <option key={e.event_id} value={e.event_id}>{e.event_id} — {e.severity || "unscored"}</option>)}
                </select>
                {current && (current.is_demo ? <DemoBadge /> : <LiveBadge />)}
                <button onClick={generate} disabled={busy || !selected} className="btn px-4 py-2">
                  {busy ? "Generating…" : "Generate"}
                </button>
              </div>
              {error && <p className="mt-2 text-xs text-sev-critical">{error}</p>}
              {report && (
                <div className="mt-3">
                  <button onClick={downloadReportJson} className="link-action">Download full report (JSON) ↓</button>
                  <pre className="scrollbar-thin mt-2 max-h-[420px] overflow-auto rounded border border-base-700 bg-base-900 p-3 text-[10px] leading-relaxed text-base-300">{JSON.stringify(report, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </Panel>
      </div>

      <Panel variant="section" title="Historical incident report" sub="A historical reference record with its context. Cannot be mistaken for a current FIRMS detection.">
        <div className="flex flex-wrap items-center gap-2">
          <select value={incidentId} onChange={(e) => setIncidentId(e.target.value)} aria-label="Historical incident" className="min-w-[280px] flex-1 rounded border border-base-600 bg-base-800 px-2 py-2 text-sm text-base-100 focus:border-accent focus:outline-none">
            {incidents.map((i) => <option key={i.incident_id} value={i.incident_id}>{i.incident_id} — {i.name} ({i.date})</option>)}
          </select>
          <HistoricalBadge compact />
          <button onClick={generateIncident} disabled={incidentBusy || !incidentId} className="btn-secondary px-4 py-2">
            {incidentBusy ? "Generating…" : "Download JSON"}
          </button>
        </div>
      </Panel>
    </div>
  );
}
