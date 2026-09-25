import Link from "next/link";
import { notFound } from "next/navigation";
import { EventReplayPlayer } from "@/components/EventReplayPlayer";
import { PageHeader, Panel } from "@/components/Panel";
import { RiskTrajectoryChart } from "@/components/RiskTrajectoryChart";
import { api, ApiError } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReplayPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  let replay, event;
  try {
    [replay, event] = await Promise.all([api.getReplay(eventId), api.getEvent(eventId)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const [facility, trajectory] = await Promise.all([
    event.facility_id ? api.getFacility(event.facility_id).catch(() => null) : Promise.resolve(null),
    api.getTrajectory(eventId).catch(() => null),
  ]);

  return (
    <div className="space-y-3">
      <PageHeader
        title={`Replay · ${event.event_id}`}
        sub={`Chronological replay of ${event.observation_count} recorded observation(s). Risk and deviation come from the same engine as the Risk Trajectory.`}
        action={<Link href={`/investigation/${event.event_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">← Investigation</Link>}
      />
      <Panel><EventReplayPlayer replay={replay} event={event} facility={facility} /></Panel>
      {trajectory && <Panel title="Risk trajectory (full history)"><RiskTrajectoryChart trajectory={trajectory} /></Panel>}
    </div>
  );
}
