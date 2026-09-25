import { DataRow } from "@/components/Panel";
import { acqUtc, confidenceCounts, satelliteName } from "@/lib/firms";
import { fmtNum } from "@/lib/format";
import type { ThermalEvent, ThermalObservation } from "@/types/domain";

/** ONLY what NASA measured (plus counts of it). No OrbiFlare risk, severity or ML output appears here. */
export function NasaObservationRows({ event, observations, sourceLabel }: { event: ThermalEvent; observations: ThermalObservation[]; sourceLabel: string }) {
  const sats = Array.from(new Set(observations.map((o) => o.satellite).filter((s): s is string => !!s)));
  const times = observations.map((o) => o.timestamp).sort();
  const bt5 = observations.map((o) => o.brightness_temperature_11).filter((v): v is number => v != null);
  return (
    <div data-testid="nasa-observation">
      <DataRow label="Source" value={sourceLabel || "NASA FIRMS"} mono={false} />
      <DataRow label="Satellite" value={sats.length ? sats.map((s) => `${satelliteName(s)} (${s})`).join(", ") : "—"} mono={false} />
      <DataRow label="FIRMS confidence" value={confidenceCounts(observations)} mono={false} />
      <DataRow label="Peak / mean FRP" value={`${fmtNum(event.peak_frp, 2)} / ${fmtNum(event.mean_frp, 2)} MW`} />
      <DataRow label="Peak / mean BT (I-4)" value={`${fmtNum(event.peak_bt, 1)} / ${fmtNum(event.mean_bt, 1)} K`} />
      {bt5.length > 0 && <DataRow label="Peak BT (I-5)" value={`${fmtNum(Math.max(...bt5), 1)} K`} />}
      {times.length > 0 && <DataRow label="First acquisition" value={acqUtc(times[0])} />}
      {times.length > 0 && <DataRow label="Last acquisition" value={acqUtc(times[times.length - 1])} />}
      <DataRow label="Observations / duration" value={`${event.observation_count} over ${fmtNum(event.duration_hours)} h`} />
      <DataRow label="Footprint radius" value={`${fmtNum(event.footprint_radius_km, 2)} km`} />
    </div>
  );
}
