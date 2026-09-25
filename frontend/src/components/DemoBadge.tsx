// Provenance badges. Three distinct, restrained treatments so data origin is never ambiguous:
//   DEMO       -- solid dark (synthetic)     LIVE -- green outline (FIRMS)     HISTORICAL -- indigo outline (reference)

export function DemoBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center rounded border border-base-100 bg-base-100 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-base-850"
      title="Demonstration data -- not a real NASA FIRMS observation"
    >
      DEMO
    </span>
  );
}

export function LiveBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center rounded border border-sev-low/60 bg-sev-low/10 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-sev-low"
      title="Real NASA FIRMS thermal observation -- not demo data"
    >
      {compact ? "LIVE" : "LIVE / NASA FIRMS"}
    </span>
  );
}

/** Source of a LIVE event, built from the FIRMS products actually present on its observations (never for synthetic data). */
export function FirmsSourceBadge({ label }: { label: string }) {
  return (
    <span
      className="inline-flex items-center rounded border border-sev-low/60 bg-sev-low/10 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-sev-low"
      title="Real NASA FIRMS thermal observations"
    >
      {label}
    </span>
  );
}

/** Provenance of a facility record (OSM / GPPD / synthetic) -- a facility is context, not a NASA detection. */
export function FacilitySourceBadge({ source, isDemo }: { source: string; isDemo: boolean }) {
  if (isDemo) return <DemoBadge compact />;
  return (
    <span className="inline-flex items-center rounded border border-base-600 bg-base-800 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-base-300" title={`Facility record source: ${source}`}>
      {source}
    </span>
  );
}

/** Historical reference record: never confused with LIVE or DEMO. */
export function HistoricalBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center rounded border border-info/50 bg-info/10 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-info"
      title="Historical reference record -- not a FIRMS detection and not a live alert"
    >
      {compact ? "HISTORICAL" : "HISTORICAL REFERENCE · NOT A LIVE FIRMS DETECTION"}
    </span>
  );
}
