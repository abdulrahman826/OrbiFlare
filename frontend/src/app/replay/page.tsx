import Link from "next/link";
import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { Panel } from "@/components/Panel";
import { RiskBadge } from "@/components/RiskBadge";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ReplayIndexPage() {
  const events = await api.listEvents();
  const replayable = [...events].filter((e) => e.observation_count >= 2).sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Event Replay</h1>
        <p className="text-sm text-base-400">Select an event to replay its real observation history chronologically.</p>
      </div>
      <Panel>
        <div className="divide-y divide-base-700/60">
          {replayable.map((e) => (
            <Link key={e.event_id} href={`/replay/${e.event_id}`} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0 hover:text-accent">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm">{e.event_id}</span>
                {e.is_demo ? <DemoBadge compact /> : <LiveBadge compact />}
                <span className="text-xs text-base-500">{fmtDate(e.first_detected)}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-base-400">{e.observation_count} observations</span>
                <RiskBadge severity={e.severity} score={e.risk_score} size="sm" />
              </div>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  );
}
