"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { HistoricalBadge } from "@/components/DemoBadge";
import { LayerControl } from "@/components/LayerControl";
import { INCIDENT_HEX, INCIDENT_LETTER, MapPanel, SEVERITY_HEX } from "@/components/MapPanel";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { RiskBadge } from "@/components/RiskBadge";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { AdminFeatureCollection, Facility, HistoricalIncident, IncidentKind, Severity, ThermalEvent, ThermalObservation } from "@/types/domain";

const SEVS: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const KINDS: { key: IncidentKind; label: string }[] = [
  { key: "REPORTED_INDUSTRIAL_INCIDENT", label: "Reported incident" },
  { key: "PERSISTENT_THERMAL_SOURCE_REFERENCE", label: "Persistent / flare source" },
  { key: "AGRICULTURAL_BURNING_REFERENCE", label: "Agricultural burning" },
  { key: "MEMORIAL_SITE_REFERENCE", label: "Memorial site" },
];

type AdminLevel = "off" | "state" | "district";

export default function GisExplorerPage() {
  const [events, setEvents] = useState<ThermalEvent[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [observations, setObservations] = useState<ThermalObservation[]>([]);
  const [incidents, setIncidents] = useState<HistoricalIncident[]>([]);
  const [admin, setAdmin] = useState<Partial<Record<"state" | "district", AdminFeatureCollection>>>({});
  const [adminLevel, setAdminLevel] = useState<AdminLevel>("state");
  const [adminError, setAdminError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [show, setShow] = useState({ events: true, firms: true, demoObs: false, facilities: false, incidents: true });
  const [sev, setSev] = useState<Severity | null>(null);
  const [kind, setKind] = useState<IncidentKind | null>(null);
  const [facType, setFacType] = useState("");
  const [tab, setTab] = useState<"events" | "incidents">("events");

  useEffect(() => {
    Promise.all([api.listEvents(), api.listFacilities(), api.listObservations(), api.listIncidents()])
      .then(([e, f, o, i]) => { setEvents(e); setFacilities(f); setObservations(o); setIncidents(i); })
      .catch((err) => setError(String(err?.message ?? err)));
  }, []);

  // Boundary geometry is fetched lazily, once per level (districts are ~1 MB).
  useEffect(() => {
    if (adminLevel === "off" || admin[adminLevel]) return;
    api.adminRegions(adminLevel).then((fc) => setAdmin((a) => ({ ...a, [adminLevel]: fc }))).catch((err) => setAdminError(String(err?.message ?? err)));
  }, [adminLevel, admin]);

  const facTypes = useMemo(() => Array.from(new Set(facilities.map((f) => f.facility_type))).sort(), [facilities]);
  const visibleEvents = useMemo(() => (show.events ? events.filter((e) => !sev || e.severity === sev) : []), [events, show.events, sev]);
  const visibleFacilities = useMemo(() => (show.facilities ? facilities.filter((f) => !facType || f.facility_type === facType) : []), [facilities, show.facilities, facType]);
  const visibleIncidents = useMemo(() => (show.incidents ? incidents.filter((i) => !kind || i.record_kind === kind) : []), [incidents, show.incidents, kind]);
  const firmsObs = useMemo(() => observations.filter((o) => o.source === "FIRMS"), [observations]);
  const demoObs = useMemo(() => observations.filter((o) => o.source !== "FIRMS"), [observations]);
  const visibleObs = useMemo(() => [...(show.firms ? firmsObs : []), ...(show.demoObs ? demoObs : [])], [show.firms, show.demoObs, firmsObs, demoObs]);
  const adminFc = adminLevel === "off" ? null : admin[adminLevel] ?? null;
  const ranked = useMemo(() => [...visibleEvents].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 40), [visibleEvents]);
  const toggle = (k: keyof typeof show) => setShow((s) => ({ ...s, [k]: !s[k] }));

  return (
    <div className="space-y-3">
      <PageHeader
        title="GIS Explorer"
        sub="Live-pipeline thermal events, raw observations and facilities alongside HISTORICAL reference incidents and real India administrative boundaries. Only layers backed by real data are offered; no satellite-imagery layer is configured."
      />
      {error && <StateBlock kind="error" title="Could not load map data">{error}</StateBlock>}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[240px_minmax(0,1fr)_310px]">
        <Panel title="Layers">
          <LayerControl
            layers={[
              { key: "events", label: `Thermal events (${events.length})`, enabled: show.events, color: SEVERITY_HEX.HIGH },
              { key: "firms", label: `FIRMS observations (${firmsObs.length})`, enabled: show.firms, color: "#1F2421" },
              { key: "demoObs", label: `Demo observations (${demoObs.length})`, enabled: show.demoObs, color: "#A39C88" },
              { key: "facilities", label: `Facilities with FIRMS context (${facilities.length})`, enabled: show.facilities, color: "#1F2421" },
              { key: "incidents", label: `Historical incidents (${incidents.length})`, enabled: show.incidents, color: INCIDENT_HEX },
            ]}
            onToggle={(key) => toggle(key as keyof typeof show)}
          />

          <p className="mt-3 text-[10px] leading-snug text-base-400">A FIRMS observation is a satellite thermal detection, not a confirmed fire.</p>

          <fieldset className="mt-4 border-t border-base-700 pt-3">
            <legend className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-base-400">Administrative boundaries</legend>
            {(["off", "state", "district"] as const).map((lvl) => (
              <label key={lvl} className="flex cursor-pointer items-center gap-2 py-0.5 text-xs text-base-200">
                <input type="radio" name="admin" checked={adminLevel === lvl} onChange={() => setAdminLevel(lvl)} className="accent-accent" />
                {lvl === "off" ? "Off" : lvl === "state" ? "States (36)" : "Districts (760)"}
              </label>
            ))}
            {adminError && <p className="mt-1 text-[11px] text-sev-critical">Boundaries unavailable: {adminError}</p>}
            {adminLevel !== "off" && !adminFc && !adminError && <p className="mt-1 text-[11px] text-base-400">Loading geometry…</p>}
            {adminFc && <p className="mt-1 text-[10px] leading-snug text-base-500">{adminFc.provenance.note}</p>}
          </fieldset>

          <div className="mt-4 border-t border-base-700 pt-3">
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-base-400">Event severity</div>
            <div className="flex flex-wrap gap-1.5">
              {SEVS.map((s) => (
                <button key={s} aria-pressed={sev === s} onClick={() => setSev(sev === s ? null : s)}
                  className={cn("flex items-center gap-1.5 rounded border px-2 py-1 text-[11px]", sev === s ? "border-accent text-accent-bright" : "border-base-600 text-base-300 hover:border-base-400")}>
                  <span className="h-2 w-2 rounded-full" style={{ background: SEVERITY_HEX[s] }} />
                  {s} <span className="font-mono text-base-400">{events.filter((e) => e.severity === s).length}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 border-t border-base-700 pt-3">
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-base-400">Historical record kind</div>
            <div className="flex flex-col gap-1">
              {KINDS.map((k) => (
                <button key={k.key} aria-pressed={kind === k.key} onClick={() => setKind(kind === k.key ? null : k.key)}
                  className={cn("flex items-center gap-1.5 rounded border px-2 py-1 text-left text-[11px]", kind === k.key ? "border-info text-info" : "border-base-600 text-base-300 hover:border-base-400")}>
                  <span className="inline-flex h-3 w-3 rotate-45 items-center justify-center" style={{ background: INCIDENT_HEX }}>
                    <span className="-rotate-45 font-mono text-[7px] font-bold text-base-950">{INCIDENT_LETTER[k.key]}</span>
                  </span>
                  <span className="flex-1">{k.label}</span>
                  <span className="font-mono text-base-400">{incidents.filter((i) => i.record_kind === k.key).length}</span>
                </button>
              ))}
            </div>
          </div>

          <label className="mt-4 block border-t border-base-700 pt-3 text-[10px] font-semibold uppercase tracking-wider text-base-400">
            Facility type
            <select value={facType} onChange={(e) => setFacType(e.target.value)} className="mt-1 w-full rounded border border-base-600 bg-base-800 px-2 py-1 text-xs font-normal normal-case tracking-normal text-base-100 focus:border-accent focus:outline-none">
              <option value="">All</option>
              {facTypes.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </label>
        </Panel>

        <Panel
          title={`Map · ${visibleEvents.length} events · ${visibleFacilities.length} facilities · ${visibleIncidents.length} historical${visibleObs.length ? ` · ${visibleObs.length} obs` : ""}`}
          flush
        >
          <div className="p-2">
            <MapPanel events={visibleEvents} facilities={visibleFacilities} observations={visibleObs} incidents={visibleIncidents} adminGeoJson={adminFc} height={620} />
          </div>
        </Panel>

        <Panel title="In view" flush>
          <div role="tablist" className="flex border-b border-base-700">
            {(["events", "incidents"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={cn("flex-1 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider", tab === t ? "border-b-2 border-accent text-accent-bright" : "text-base-400 hover:text-base-200")}>
                {t === "events" ? `Events ${visibleEvents.length}` : `Historical ${visibleIncidents.length}`}
              </button>
            ))}
          </div>
          <ul className="scrollbar-thin max-h-[610px] divide-y divide-base-700/60 overflow-y-auto">
            {tab === "events" && ranked.length === 0 && <li className="p-3"><StateBlock kind="empty" title="No events match the filters" /></li>}
            {tab === "events" && ranked.map((e) => (
              <li key={e.event_id}>
                <Link href={`/investigation/${e.event_id}`} className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-base-800/70">
                  <span className="font-mono text-[11px] text-base-100">{e.event_id}</span>
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-base-400">{e.is_demo ? "DEMO" : "LIVE"}</span>
                    <RiskBadge severity={e.severity} score={e.risk_score} size="sm" />
                  </span>
                </Link>
              </li>
            ))}
            {tab === "incidents" && visibleIncidents.length === 0 && <li className="p-3"><StateBlock kind="empty" title="No historical records match" /></li>}
            {tab === "incidents" && visibleIncidents.map((i) => (
              <li key={i.incident_id}>
                <Link href={`/incidents/${i.incident_id}`} className="block px-3 py-2 hover:bg-base-800/70">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-base-100">{i.name}</span>
                    <HistoricalBadge compact />
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] text-base-400">{i.incident_id} · {i.date} · {i.state} · {i.record_kind_label}</div>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
