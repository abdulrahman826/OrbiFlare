import { DataRow } from "@/components/Panel";
import { facilityContextView, NEARBY_NOTE } from "@/lib/assessment";
import { facilityTypeLabel } from "@/lib/format";
import type { FacilityContext } from "@/types/domain";

const Q_TONE: Record<string, string> = {
  High: "border-sev-low/50 bg-sev-low/10 text-sev-low",
  Medium: "border-sev-medium/50 bg-sev-medium/10 text-sev-medium",
  Low: "border-base-500 bg-base-800 text-base-300",
};

/** Facility context as ASSOCIATION ONLY: distance, type, source and an explicit quality grade. Never attribution. */
export function FacilityContextSection({ ctx }: { ctx: FacilityContext | null }) {
  const v = facilityContextView(ctx);
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-2 lg:grid-cols-2" data-testid="facility-context">
      <div>
        <p className="mb-2 text-xs text-base-200">{v.headline}</p>
        {v.rows.map((r) => (
          <DataRow
            key={r.label}
            label={r.label}
            mono={r.label === "Distance" || r.label === "Nearby facilities"}
            value={
              r.label === "Facility context quality" ? (
                <span className={`rounded border px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider ${Q_TONE[r.value] ?? Q_TONE.Low}`}>{r.value}</span>
              ) : r.label === "Facility type" ? facilityTypeLabel(r.value) : r.value
            }
          />
        ))}
        {v.meaning && <p className="mt-2 text-[11px] text-base-300" data-testid="quality-meaning">{v.meaning}</p>}
        {v.limitation && <p className="mt-2 rounded border border-sev-medium/40 bg-sev-medium/5 px-2 py-1 text-[11px] text-base-200">{v.limitation}</p>}
      </div>
      <div>
        <p className="mb-2 text-[11px] text-base-400" data-testid="attribution-note">{v.attribution}</p>
        {ctx && ctx.nearby.length > 0 && (
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-base-400">
                <th className="pb-1 font-medium">Facility</th><th className="pb-1 font-medium">Type</th><th className="pb-1 font-medium">Quality</th>
                <th className="pb-1 text-right font-medium">km</th><th className="pb-1 text-right font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {ctx.nearby.slice(0, 6).map((f) => (
                <tr key={f.facility_id} className="border-t border-base-700">
                  <td className="py-1 pr-2 text-base-100">{f.name}</td>
                  <td className="py-1 pr-2 text-base-300">{facilityTypeLabel(f.facility_type)}</td>
                  <td className="py-1 pr-2 text-base-300">{f.context_quality ? f.context_quality.charAt(0) + f.context_quality.slice(1).toLowerCase() : "—"}</td>
                  <td className="py-1 text-right font-mono">{f.distance_km.toFixed(2)}</td>
                  <td className="py-1 text-right font-mono text-base-400">{f.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-2 text-[11px] leading-snug text-base-400">{NEARBY_NOTE} {ctx?.distance_note}</p>
        {ctx?.quality_note && <p className="mt-1 text-[11px] leading-snug text-base-500">{ctx.quality_note}</p>}
      </div>
    </div>
  );
}
