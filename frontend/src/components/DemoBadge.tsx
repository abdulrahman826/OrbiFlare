export function DemoBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent"
      title="Synthetic demonstration data -- not a real NASA FIRMS observation"
    >
      {compact ? "DEMO" : "DEMO / SYNTHETIC"}
    </span>
  );
}

export function LiveBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400"
      title="Real NASA FIRMS thermal observation -- not synthetic/demo data"
    >
      {compact ? "LIVE" : "LIVE / NASA FIRMS"}
    </span>
  );
}
