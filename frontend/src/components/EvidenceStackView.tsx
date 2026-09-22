import { cn } from "@/lib/cn";
import type { EvidenceItem, EvidenceStack } from "@/types/domain";

function Item({ item, icon, tone }: { item: EvidenceItem; icon: string; tone: string }) {
  return (
    <li className="flex gap-2 text-xs leading-relaxed">
      <span className={cn("mt-0.5 shrink-0", tone)}>{icon}</span>
      <span className="text-base-200">
        <span className="text-base-400">[{item.category}]</span> {item.explanation}
      </span>
    </li>
  );
}

export function EvidenceStackView({ evidence }: { evidence: EvidenceStack }) {
  return (
    <div className="space-y-4">
      {evidence.supporting_evidence.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-sev-low">Supporting</div>
          <ul className="space-y-1.5">
            {evidence.supporting_evidence.map((e, i) => (
              <Item key={i} item={e} icon="✓" tone="text-sev-low" />
            ))}
          </ul>
        </div>
      )}
      {evidence.contradicting_evidence.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-base-300">Contradicting / within normal range</div>
          <ul className="space-y-1.5">
            {evidence.contradicting_evidence.map((e, i) => (
              <Item key={i} item={e} icon="•" tone="text-base-400" />
            ))}
          </ul>
        </div>
      )}
      {evidence.uncertain_evidence.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-400">Uncertainty</div>
          <ul className="space-y-1.5">
            {evidence.uncertain_evidence.map((e, i) => (
              <Item key={i} item={e} icon="⚠" tone="text-amber-400" />
            ))}
          </ul>
        </div>
      )}
      {evidence.unavailable_evidence.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-base-400">Unavailable</div>
          <ul className="space-y-1.5">
            {evidence.unavailable_evidence.map((e, i) => (
              <Item key={i} item={e} icon="–" tone="text-base-500" />
            ))}
          </ul>
        </div>
      )}
      {evidence.correlation_notes.length > 0 && (
        <div className="rounded border border-base-600/60 bg-base-800/60 p-2.5">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-base-300">Correlation notes</div>
          {evidence.correlation_notes.map((n, i) => (
            <p key={i} className="text-[11px] leading-relaxed text-base-400">
              {n}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
