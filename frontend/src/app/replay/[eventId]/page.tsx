import { notFound } from "next/navigation";
import { EventReplayPlayer } from "@/components/EventReplayPlayer";
import { Panel } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReplayPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  let replay;
  let event;
  try {
    [replay, event] = await Promise.all([api.getReplay(eventId), api.getEvent(eventId)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-mono text-lg font-semibold text-base-100">Replay: {event.event_id}</h1>
        <p className="text-sm text-base-400">Chronological replay of {event.observation_count} real recorded observation(s).</p>
      </div>
      <Panel>
        <EventReplayPlayer replay={replay} />
      </Panel>
    </div>
  );
}
