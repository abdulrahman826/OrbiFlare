"use client";

import { useState } from "react";
import { OperatorActions } from "@/components/OperatorActions";
import type { AlertState } from "@/types/domain";

export function OperatorActionsSection({ eventId, initialState }: { eventId: string; initialState: AlertState }) {
  const [state, setState] = useState(initialState);
  return (
    <div>
      <p className="mb-2 text-xs text-base-400">
        Current state: <span className="font-mono font-semibold text-base-100">{state}</span>
      </p>
      <OperatorActions eventId={eventId} currentState={state} onChanged={setState} />
    </div>
  );
}
