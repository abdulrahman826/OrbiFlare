"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { AlertState } from "@/types/domain";

const TRANSITIONS: Record<AlertState, AlertState[]> = {
  DETECTED: ["VALIDATING", "ALERTED"],
  VALIDATING: ["ALERTED", "MONITORING", "EXTINGUISHED"],
  ALERTED: ["ESCALATED", "MONITORING", "EXTINGUISHED"],
  ESCALATED: ["MONITORING", "EXTINGUISHED"],
  MONITORING: ["ESCALATED", "EXTINGUISHED", "ALERTED"],
  EXTINGUISHED: [],
};

const LABELS: Record<AlertState, string> = {
  DETECTED: "Detected", VALIDATING: "Validate", ALERTED: "Alert", ESCALATED: "Escalate",
  MONITORING: "Monitor", EXTINGUISHED: "Resolve / Extinguish",
};

export function OperatorActions({ eventId, currentState, onChanged }: { eventId: string; currentState: AlertState; onChanged?: (s: AlertState) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const options = TRANSITIONS[currentState] || [];

  async function act(to: AlertState) {
    setBusy(true);
    setError(null);
    try {
      await api.transitionEvent(eventId, to, "operator");
      onChanged?.(to);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transition failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {options.length === 0 && <span className="text-xs text-base-400">No further transitions -- event is {currentState}.</span>}
        {options.map((s) => (
          <button
            key={s}
            disabled={busy}
            onClick={() => act(s)}
            className={cn(s === "EXTINGUISHED" ? "btn-secondary" : "btn")}
          >
            {LABELS[s]}
          </button>
        ))}
      </div>
      {error && <p className="mt-2 text-xs text-sev-critical">{error}</p>}
      <p className="mt-2 text-[11px] text-base-500">All state changes are explicit operator actions and are fully audited. The system never autonomously marks an event Extinguished.</p>
    </div>
  );
}
