import { INTERP_HEX, strengthText } from "@/lib/interpretation";
import type { SourceInterpretation } from "@/types/domain";

/** Source interpretation near the top of an investigation: candidate label, strength, the evidence behind it and the alternatives. Never a confirmed fire. */
export function SourceInterpretationPanel({ si }: { si: SourceInterpretation | null | undefined }) {
  if (!si) return null;
  const c = INTERP_HEX[si.classification] ?? INTERP_HEX.UNCERTAIN;
  return (
    <section className="rounded border border-base-600 bg-base-850" data-testid="source-interpretation">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-base-700 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full border border-base-500" style={{ background: c.fill }} aria-hidden />
          <h2 className="text-[11px] font-bold uppercase tracking-[0.12em] text-base-100">Source interpretation</h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-base-400">candidate label · not a confirmed fire</span>
      </div>
      <div className="grid grid-cols-1 gap-x-8 gap-y-3 p-3 lg:grid-cols-2">
        <div>
          <div className="text-base font-semibold text-base-100">{si.label}</div>
          <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-base-400" data-testid="interp-strength">{strengthText(si.strength)}</div>
          <p className="mt-2 text-xs text-base-300">{si.meaning}</p>
          {si.alternative_explanations.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Alternative explanations</div>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-base-300">{si.alternative_explanations.map((a, i) => <li key={`${a}-${i}`}>{a}</li>)}</ul>
            </div>
          )}
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Why?</div>
          {si.supporting_evidence.length === 0 ? (
            <p className="mt-1 text-xs text-base-300">No supporting evidence for a specific source interpretation.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-xs text-base-200">{si.supporting_evidence.map((x, i) => <li key={`${x.signal}-${i}`}>• {x.text}</li>)}</ul>
          )}
          {si.contradicting_evidence.length > 0 && (
            <>
              <div className="mt-3 text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Against or limiting</div>
              <ul className="mt-1 space-y-1 text-xs text-base-300">{si.contradicting_evidence.map((x, i) => <li key={`${x.signal}-${i}`}>• {x.text}</li>)}</ul>
            </>
          )}
          {si.unavailable_evidence.length > 0 && (
            <>
              <div className="mt-3 text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Unavailable</div>
              <ul className="mt-1 space-y-1 text-xs text-base-400">{si.unavailable_evidence.map((x, i) => <li key={`${x}-${i}`}>– {x}</li>)}</ul>
            </>
          )}
        </div>
      </div>
      <p className="border-t border-base-700 px-3 py-1.5 text-[11px] text-base-400">{si.disclaimer} {si.facility_note}</p>
    </section>
  );
}
