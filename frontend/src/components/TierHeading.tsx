/** Section marker so the Investigation reads as: NASA observation -> context -> behaviour -> assessment -> limitations. */
export function TierHeading({ n, label, sub }: { n: number; label: string; sub: string }) {
  return (
    <div className="mt-5 flex flex-wrap items-baseline gap-x-3 border-b-2 border-base-100 pb-1">
      <span className="font-mono text-xs text-base-400">{String(n).padStart(2, "0")}</span>
      <h2 className="text-[13px] font-bold uppercase tracking-[0.14em] text-base-100">{label}</h2>
      <span className="text-[11px] text-base-400">{sub}</span>
    </div>
  );
}
