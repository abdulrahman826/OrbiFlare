import Link from "next/link";
import { IncidentTable } from "@/components/IncidentTable";
import { KPI } from "@/components/KPI";
import { PageHeader, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  let data;
  try {
    data = await Promise.all([api.listIncidents(), api.incidentSummary()]);
  } catch {
    return <StateBlock kind="error" title="Historical reference data unavailable">The backend could not be reached.</StateBlock>;
  }
  const [incidents, summary] = data;
  const kinds = summary.by_record_kind;

  return (
    <div className="space-y-3">
      <PageHeader
        title="Historical reference incidents"
        sub="A curated historical dataset, kept separate from live FIRMS observations, thermal events, facilities and demo data. It is not used to train or score anything."
        action={<Link href="/gis" className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Open on map →</Link>}
      />
      <div className="rounded border border-info/30 bg-info/5 px-3 py-2 text-xs text-base-200">
        <b className="text-info">HISTORICAL · NOT A FIRMS DETECTION.</b> {summary.provenance.firms_match_note} Locations are approximate and per-record claims are as supplied by the listed source; OrbiFlare has not verified them.
      </div>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-5">
        <KPI label="Records" value={summary.total} sub={summary.date_range ? `${summary.date_range[0].slice(0, 4)}–${summary.date_range[1].slice(0, 4)}` : undefined} />
        <KPI label="Reported incidents" value={kinds.REPORTED_INDUSTRIAL_INCIDENT ?? 0} />
        <KPI label="Persistent / flare sources" value={kinds.PERSISTENT_THERMAL_SOURCE_REFERENCE ?? 0} sub="not discrete fires" />
        <KPI label="Agricultural refs" value={kinds.AGRICULTURAL_BURNING_REFERENCE ?? 0} />
        <KPI label="Memorial refs" value={kinds.MEMORIAL_SITE_REFERENCE ?? 0} />
      </div>
      <IncidentTable incidents={incidents} />
    </div>
  );
}
