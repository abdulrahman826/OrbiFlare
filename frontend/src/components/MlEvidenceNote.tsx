import { ML_CORRELATION_NOTE, ML_OVERLAP_NOTE, ML_ROLE_NOTE } from "@/lib/assessment";

/** The RF's proxy Class A label was derived from facility proximity and persistence; it is not independent of those factors. */
export function MlEvidenceNote() {
  return (
    <div className="mt-3 rounded border border-sev-medium/40 bg-sev-medium/5 px-2.5 py-1.5 text-[11px] leading-snug text-base-200" data-testid="ml-note">
      <b>ML evidence, not a verdict.</b> {ML_ROLE_NOTE} {ML_OVERLAP_NOTE} {ML_CORRELATION_NOTE}
    </div>
  );
}
