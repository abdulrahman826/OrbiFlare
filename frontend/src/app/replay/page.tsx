import Link from "next/link";
import { DemoBadge, LiveBadge } from "@/components/DemoBadge";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ReplayIndexPage() {
  const events = await api.listEvents().catch(() => null);
  if (!events) return <StateBlock kind="error" title="Backend unavailable" />;
  const replayable = events.filter((e) => e.observation_count >= 2).sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));

  return (
    <div className="space-y-3">
      <PageHeader title="Event Replay" sub="Select an event to replay its real observation history. Events with fewer than 2 observations are not replayable." />
      <Panel flush>
        {replayable.length === 0 && <div className="p-3"><StateBlock kind="empty" title="No replayable events" /></div>}
        <ul className="divide-y divide-base-700/60">
          {replayable.map((e) => (
            <li key={e.event_id}>
              <Link href={`/replay/${e.event_id}`} className="flex flex-wrap items-center justify-between gap-3 px-3 py-2 hover:bg-base-800/70">
                <div className="flex items-center gap-2">
                  <RiskBadge severity={e.severity} score={e.risk_score} size="sm" />
                  <span className="font-mono text-xs text-base-100">{e.event_id}</span>
                  {e.is_demo ? <DemoBadge compact /> : <LiveBadge compact />}
                  <span className="font-mono text-[11px] text-base-400">{fmtDate(e.first_detected)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-base-400">{e.observation_count} obs</span>
                  <TrajectoryBadge direction={e.trajectory_direction} />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">Replay →</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
