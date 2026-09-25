import type { Risk } from "@/types/domain";

function List({ title, items, tone }: { title: string; items?: string[]; tone: string }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className={`text-[10px] font-bold uppercase tracking-[0.1em] ${tone}`}>{title}</div>
      <ul className="mt-1 space-y-0.5">
        {items.map((t, i) => <li key={i} className="text-xs text-base-200">– {t}</li>)}
      </ul>
    </div>
  );
}

/** Why this severity, what supports it, what limits it, what is missing, and what WOULD raise it (conditional, never a forecast). */
export function RiskExplanation({ risk }: { risk: Risk }) {
  return (
    <div className="space-y-3" data-testid="risk-explanation">
      <p className="text-xs text-base-100">{risk.severity_reason || risk.explanation}</p>
      <div className="grid grid-cols-1 gap-x-8 gap-y-3 lg:grid-cols-2">
        <List title="Contributing evidence" items={risk.contributing} tone="text-sev-low" />
        <List title="Limiting factors" items={risk.limiting} tone="text-sev-medium" />
        <List title="Missing evidence" items={risk.missing_evidence} tone="text-base-400" />
        <List title="What would raise this score if observed" items={risk.escalation_evidence} tone="text-base-300" />
      </div>
      <p className="text-[11px] text-base-500">Risk is operational priority for analyst review. It is not fire probability, not a forecast, and not a confirmed fire.</p>
    </div>
  );
}
