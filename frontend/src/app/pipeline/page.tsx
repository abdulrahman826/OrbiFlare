import { PipelineDemo } from "@/components/PipelineDemo";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * /pipeline -- a small, standalone visual walkthrough of the OrbiFlare intelligence pipeline
 * (FIRMS -> Living Thermal Event -> Facility Thermal Twin -> Behaviour Deviation -> Evidence
 * Fusion -> Risk Trajectory -> OrbiFlare) for the SIH 2026 demo video. Every stage value shown
 * during the animation is a fixed, deterministic demo value -- it never reads or writes live
 * event data. The only live thing on this page is the destination of the closing "Open
 * investigation" link, which points at a real, currently active event so the demo can flow
 * straight into the real product.
 */
export default async function PipelinePage() {
  const flagshipEventId = await api
    .listEvents()
    .then((events) => {
      const active = events.filter((e) => e.status !== "EXTINGUISHED");
      const pool = active.length ? active : events;
      if (!pool.length) return null;
      return pool.slice().sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))[0].event_id;
    })
    .catch(() => null);

  return <PipelineDemo flagshipEventId={flagshipEventId} />;
}
