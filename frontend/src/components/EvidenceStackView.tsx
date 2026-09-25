import { cn } from "@/lib/cn";
import type { EvidenceDirection, EvidenceItem, EvidenceStack } from "@/types/domain";

const GROUPS: { key: keyof Pick<EvidenceStack, "supporting_evidence" | "contradicting_evidence" | "uncertain_evidence" | "unavailable_evidence">; dir: EvidenceDirection; label: string; icon: string; tone: string; hint: string }[] = [
  { key: "supporting_evidence", dir: "SUPPORTING", label: "Supporting", icon: "✓", tone: "text-sev-low border-sev-low/40", hint: "Favours the primary (industrial-behaviour) interpretation" },
  { key: "contradicting_evidence", dir: "CONTRADICTING", label: "Contradicting", icon: "✕", tone: "text-sev-high border-sev-high/40", hint: "Within normal range or against the primary interpretation" },
  { key: "uncertain_evidence", dir: "UNCERTAIN", label: "Uncertain", icon: "?", tone: "text-sev-medium border-sev-medium/40", hint: "Ambiguous or low-confidence" },
  { key: "unavailable_evidence", dir: "UNAVAILABLE", label: "Unavailable", icon: "–", tone: "text-base-400 border-base-600", hint: "Could not be evaluated" },
];

function Item({ item, tone, icon }: { item: EvidenceItem; tone: string; icon: string }) {
  return (
    <li className="border-b border-base-700 py-2 first:pt-0">
      <div className="flex items-center gap-2">
        <span className={cn("inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border font-mono text-[10px]", tone)}>{icon}</span>
        <span className="rounded bg-base-700 px-1.5 py-px font-mono text-[9px] font-semibold tracking-wider text-base-300">{item.category}</span>
        <span className="truncate font-mono text-[11px] text-base-200">{item.name}</span>
        {item.strength && <span className="ml-auto shrink-0 text-[9px] font-semibold uppercase tracking-wider text-base-400">{item.strength}</span>}
      </div>
      <p className="mt-1 text-xs leading-relaxed text-base-200">{item.explanation}</p>
      <div className="mt-1 flex flex-wrap gap-x-4 text-[10px] text-base-400">
        {item.observed_value !== null && <span>observed <b className="font-mono text-base-200">{item.observed_value}</b></span>}
        {item.expected_value !== null && <span>expected <b className="font-mono text-base-200">{item.expected_value}</b></span>}
        <span>source {item.source}</span>
        {item.related_to.length > 0 && <span className="text-sev-medium">correlated with: {item.related_to.join(", ")}</span>}
      </div>
    </li>
  );
}

export function EvidenceStackView({ evidence }: { evidence: EvidenceStack }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {GROUPS.map((g) => (
          <span key={g.dir} className={cn("rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider", g.tone)}>
            {g.label} <span className="font-mono">{evidence[g.key].length}</span>
          </span>
        ))}
      </div>
      {GROUPS.map((g) =>
        evidence[g.key].length > 0 ? (
          <div key={g.dir}>
            <div className="mb-1.5 flex items-baseline gap-2">
              <span className={cn("text-[11px] font-semibold uppercase tracking-wider", g.tone.split(" ")[0])}>{g.label}</span>
              <span className="text-[10px] text-base-500">{g.hint}</span>
            </div>
            <ul className="space-y-1.5">
              {evidence[g.key].map((e, i) => <Item key={`${g.dir}-${i}`} item={e} tone={g.tone} icon={g.icon} />)}
            </ul>
          </div>
        ) : null
      )}
      {evidence.correlation_notes.length > 0 && (
        <div className="rounded border border-sev-medium/30 bg-sev-medium/5 p-2.5">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-sev-medium">Correlation-aware fusion</div>
          {evidence.correlation_notes.map((n, i) => (
            <p key={i} className="text-[11px] leading-relaxed text-base-300">{n}</p>
          ))}
        </div>
      )}
    </div>
  );
}
