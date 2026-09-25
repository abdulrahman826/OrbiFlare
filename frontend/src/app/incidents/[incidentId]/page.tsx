import Link from "next/link";
import { notFound } from "next/navigation";
import { DemoBadge, HistoricalBadge } from "@/components/DemoBadge";
import { IncidentReportButton } from "@/components/IncidentReportButton";
import { MapPanel } from "@/components/MapPanel";
import { DataRow, Panel, StateBlock } from "@/components/Panel";
import { RiskBadge } from "@/components/RiskBadge";
import { api, ApiError } from "@/lib/api";
import { fmtDate, fmtNum } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function IncidentDetailPage({ params }: { params: Promise<{ incidentId: string }> }) {
  const { incidentId } = await params;
  let ctx;
  try {
    ctx = await api.getIncidentContext(incidentId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [events, facilities] = await Promise.all([api.listEvents().catch(() => []), api.listFacilities().catch(() => [])]);
  const { incident: inc, admin, firms_match: match } = ctx;
  const nearEventIds = new Set(ctx.nearby_current_events.map((e) => e.event_id));
  const nearFacIds = new Set(ctx.nearby_facilities.map((f) => f.facility_id));

  return (
    <div className="space-y-3">
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-base font-semibold text-base-100">{inc.name}</h1>
          <HistoricalBadge />
          <span className="rounded border border-base-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-base-300">{inc.record_kind_label}</span>
          <Link href="/gis" className="ml-auto text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">← GIS Explorer</Link>
        </div>
        <p className="mt-2 text-sm text-base-200">{inc.description}</p>
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-base-700 pt-2.5 md:grid-cols-4">
          {[
            ["Record", inc.incident_id], ["Date (as supplied)", inc.date],
            ["State / district", `${admin.state ?? inc.state}${admin.district ? ` / ${admin.district}` : ""}`],
            ["Facility type (as supplied)", inc.facility_type],
          ].map(([k, v]) => (
            <div key={k}><div className="text-[10px] uppercase tracking-wider text-base-400">{k}</div><div className="mt-0.5 font-mono text-xs text-base-100">{v}</div></div>
          ))}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel variant="section" title="Location context" sub="Approximate location · nearby current events and facilities within 50 km" flush>
          <div className="p-2">
            <MapPanel
              incidents={[inc]} facilities={facilities.filter((f) => nearFacIds.has(f.facility_id))} events={events.filter((e) => nearEventIds.has(e.event_id))}
              height={340} center={[inc.longitude, inc.latitude]} zoom={8}
            />
          </div>
        </Panel>
        <Panel variant="section" title="Provenance">
          <DataRow label="Source" value="Historical incident reference" mono={false} />
          <DataRow label="Dataset" value="Historical incident record" mono={false} />
          <DataRow label="Source label (as supplied)" value={inc.provenance.source_label} mono={false} />
          <DataRow label="Status" value="Historical reference — not a live FIRMS detection" mono={false} />
          <DataRow label="Live FIRMS detection" value="NO" />
          <DataRow label="Used for ML training" value="NO" />
          <DataRow label="Verified by OrbiFlare" value="NO" />
          <DataRow label="Coordinates" value="approximate" />
          <ul className="mt-2 space-y-1">{inc.coordinate_notes.map((n, i) => <li key={i} className="text-[11px] text-base-400">{n}</li>)}</ul>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title="What is known" sub="Stated by the record and by OrbiFlare's own lookups">
          <ul className="space-y-1.5 text-xs text-base-200">{ctx.known.map((k, i) => <li key={i} className="flex gap-2"><span className="text-sev-low">✓</span>{k}</li>)}</ul>
        </Panel>
        <Panel variant="section" title="What is not known" sub="Deliberately left unresolved">
          <ul className="space-y-1.5 text-xs text-base-200">{ctx.unknown.map((k, i) => <li key={i} className="flex gap-2"><span className="text-sev-medium">?</span>{k}</li>)}</ul>
        </Panel>
      </div>

      <Panel
        title="FIRMS match check"
        sub={`Stored non-demo FIRMS observations within ${match.spatial_buffer_km} km and ±${match.temporal_window_days} day of the record date`}
        action={<span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold ${match.status === "NO_FIRMS_MATCH" ? "border-base-500 text-base-300" : "border-info/40 text-info"}`}>{match.status}</span>}
      >
        <p className="text-xs text-base-200">{match.note}</p>
        <p className="mt-1 font-mono text-[11px] text-base-400">matching observations: {match.matching_firms_observations}</p>
      </Panel>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title={`Facilities within ${ctx.radius_km} km`} sub="Spatial association only · not attribution" flush>
          {ctx.nearby_facilities.length === 0 ? <div className="p-3"><StateBlock kind="empty" title="No OrbiFlare facility records nearby" /></div> : (
            <ul className="divide-y divide-base-700/60">
              {ctx.nearby_facilities.map((f) => (
                <li key={f.facility_id}>
                  <Link href={`/facilities/${f.facility_id}`} className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-base-800/70">
                    <span className="text-xs text-base-100">{f.name} <span className="text-base-400">· {f.facility_type.replace(/_/g, " ")}</span></span>
                    <span className="flex items-center gap-2 font-mono text-[11px] text-base-300">{fmtNum(f.distance_km)} km {f.is_demo && <DemoBadge compact />}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel variant="section" title={`Current thermal events within ${ctx.radius_km} km`} sub="Proximity is not causation or recurrence" flush>
          {ctx.nearby_current_events.length === 0 ? <div className="p-3"><StateBlock kind="empty" title="No current thermal events nearby" /></div> : (
            <ul className="divide-y divide-base-700/60">
              {ctx.nearby_current_events.slice(0, 15).map((e) => (
                <li key={e.event_id}>
                  <Link href={`/investigation/${e.event_id}`} className="flex items-center justify-between gap-2 px-3 py-2 hover:bg-base-800/70">
                    <span className="font-mono text-[11px] text-base-100">{e.event_id}</span>
                    <span className="flex items-center gap-2 font-mono text-[11px] text-base-300">{fmtDate(e.first_detected)} · {fmtNum(e.distance_km)} km <RiskBadge severity={e.severity} score={e.risk_score} size="sm" />{e.is_demo && <DemoBadge compact />}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel variant="section" title="Caveats">
        <ul className="space-y-1.5 text-xs text-base-300">{inc.caveats.map((c, i) => <li key={i} className="flex gap-2"><span className="text-sev-medium">△</span>{c}</li>)}</ul>
        <div className="mt-3"><IncidentReportButton incidentId={inc.incident_id} /></div>
      </Panel>
    </div>
  );
}
