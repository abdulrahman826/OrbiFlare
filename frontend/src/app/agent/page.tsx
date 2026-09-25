import { AgentPanel } from "@/components/AgentPanel";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AgentPage() {
  const [events, facilities] = await Promise.all([api.listEvents().catch(() => []), api.listFacilities().catch(() => [])]);
  const top = [...events].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  const suggestions = [
    "show escalating events",
    "which events are high risk?",
    "which events have insufficient baseline?",
    "which facility has the most persistent events?",
    "how many high risk events are active?",
    "list historical incidents in Gujarat",
    ...(top[0] ? [`why is ${top[0].event_id} high risk?`, `compare ${top[0].event_id} baseline`, `historical incidents near ${top[0].event_id}`] : []),
    ...(top.length > 1 ? [`compare ${top[0].event_id} and ${top[1].event_id}`] : []),
    ...(facilities[0] ? [`what is the normal baseline for ${facilities[0].facility_id}`] : []),
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-base-100">OrbiFlare Intelligence Console</h1>
          <p className="mt-0.5 font-mono text-[11px] uppercase tracking-[0.2em] text-base-400">Read · Compare · Summarize</p>
        </div>
        <span className="rounded border border-base-600 px-2 py-1 font-mono text-[10px] text-base-300">DETERMINISTIC · OFFLINE · READ-ONLY</span>
      </div>
      <Panel>
        <AgentPanel suggestions={suggestions} />
      </Panel>
      <p className="text-[11px] text-base-500">
        The console retrieves and compares stored intelligence through a fixed tool registry. It cannot change alert state, resolve or extinguish events, run arbitrary queries, or take action.
      </p>
    </div>
  );
}
