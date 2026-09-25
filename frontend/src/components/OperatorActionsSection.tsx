"use client";

import { useState } from "react";
import { OperatorActions } from "@/components/OperatorActions";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { AlertState, OperatorHistoryEntry } from "@/types/domain";

const LIFECYCLE: AlertState[] = ["DETECTED", "VALIDATING", "ALERTED", "ESCALATED", "MONITORING", "EXTINGUISHED"];

export function OperatorActionsSection({ eventId, initialState, initialHistory = [] }: { eventId: string; initialState: AlertState; initialHistory?: OperatorHistoryEntry[] }) {
  const [state, setState] = useState(initialState);
  const [history, setHistory] = useState(initialHistory);

  async function changed(s: AlertState) {
    setState(s);
    try { setHistory(await api.alertHistory(eventId)); } catch { /* history is best-effort display */ }
  }

  return (
    <div className="space-y-3">
      <ol className="flex flex-wrap gap-1.5" aria-label="Lifecycle">
        {LIFECYCLE.map((s) => (
          <li key={s} aria-current={s === state ? "step" : undefined}
            className={`rounded border px-2 py-0.5 font-mono text-[10px] tracking-wide ${s === state ? "border-accent/60 bg-accent/15 text-accent-bright" : "border-base-700 text-base-500"}`}>
            {s}
          </li>
        ))}
      </ol>
      <OperatorActions eventId={eventId} currentState={state} onChanged={changed} />
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-base-400">Audit trail</div>
        {history.length === 0 ? (
          <p className="text-xs text-base-500">No operator actions recorded yet.</p>
        ) : (
          <ul className="space-y-1">
            {history.map((h, i) => (
              <li key={i} className="font-mono text-[11px] text-base-300">
                {fmtDate(h.changed_at)} · {h.from_state ?? "∅"} → <span className="text-base-100">{h.to_state}</span> · {h.actor}{h.note ? ` · ${h.note}` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
