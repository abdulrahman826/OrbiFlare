"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { failedUi, formatIst, idleUi, okUi, RUNNING_UI, type RefreshUi } from "@/lib/firmsRefresh";
import type { FirmsStatus } from "@/types/domain";

/** Command Center control: real NASA FIRMS refresh, last-sync time, and an unobtrusive result message. */
export function FirmsRefreshControl({ firms }: { firms: FirmsStatus | null }) {
  const router = useRouter();
  const configured = firms?.configured ?? false;
  const [ui, setUi] = useState<RefreshUi>(idleUi(configured));
  const [syncedAt, setSyncedAt] = useState<string | null>(firms?.last_sync_at ?? null);

  async function refresh() {
    setUi(RUNNING_UI);
    const res = await api.refreshFirms();
    if (res.ok) {
      setUi(okUi(res.body));
      setSyncedAt(res.body.synced_at);
    } else {
      setUi(failedUi(res.body));
    }
    router.refresh(); // re-fetch server components: map, KPIs, telemetry bar
  }

  const tone = ui.state === "ok" ? "text-sev-low" : ui.state === "failed" ? "text-sev-critical" : "text-base-300";
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] text-base-400">Last sync: {formatIst(syncedAt)}</span>
        {firms?.manual_refresh_enabled !== false && (
          <button onClick={refresh} disabled={ui.buttonDisabled} className="btn" aria-busy={ui.state === "running"}>
            {ui.buttonLabel}
          </button>
        )}
      </div>
      {(ui.title || ui.lines.length > 0) && (
        <div role="status" aria-live="polite" className={cn("text-right text-[11px] leading-snug", tone)}>
          {ui.title && <div className="font-semibold uppercase tracking-wider">{ui.title}</div>}
          {ui.lines.map((l) => <div key={l} className="font-mono text-base-300">{l}</div>)}
        </div>
      )}
    </div>
  );
}
