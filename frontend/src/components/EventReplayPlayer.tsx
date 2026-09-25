"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPanel } from "@/components/MapPanel";
import { RiskBadge } from "@/components/RiskBadge";
import { fmtDate, fmtNum } from "@/lib/format";
import type { EventReplay, Facility, ThermalEvent, ThermalObservation } from "@/types/domain";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-base-700 bg-base-800/60 px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-base-400">{label}</div>
      <div className="font-mono text-sm text-base-100">{value}</div>
    </div>
  );
}

const BTN = "btn-secondary px-2.5 font-mono";

/** Real chronological replay. Every value comes from the backend replay frames (same engine as Risk Trajectory). */
export function EventReplayPlayer({ replay, event, facility, showMap = true }: { replay: EventReplay; event?: ThermalEvent; facility?: Facility | null; showMap?: boolean }) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frames = replay.frames;
  const idx = Math.min(step, frames.length - 1);
  const frame = frames[idx];

  useEffect(() => {
    if (!playing) return;
    if (step >= frames.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setStep((s) => Math.min(s + 1, frames.length - 1)), 900);
    return () => clearTimeout(t);
  }, [playing, step, frames.length]);

  const visibleObs: ThermalObservation[] = useMemo(() => frames.slice(0, idx + 1).map((f) => f.observation), [frames, idx]);
  const riskSoFar = frames.slice(0, idx + 1).map((f) => Math.round(f.risk_score));

  if (!frame) return <p className="text-sm text-base-400">No observations to replay.</p>;

  const partial: ThermalEvent | undefined = event && {
    ...event, centroid_lat: frame.centroid_lat, centroid_lon: frame.centroid_lon,
    severity: frame.severity, risk_score: frame.risk_score, peak_frp: frame.cumulative_peak_frp, observation_count: frame.cumulative_observation_count,
  };

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-base-400">{replay.note}</p>
      <div className={showMap ? "grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_320px]" : ""}>
        {showMap && (
          <MapPanel
            events={[]} facilities={facility ? [facility] : []} observations={visibleObs}
            height={300} center={[frame.centroid_lon, frame.centroid_lat]} zoom={11} legend={false}
            key={event?.event_id}
          />
        )}
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Step" value={`${frame.step} / ${frames.length}`} />
            <Stat label="Observations" value={String(frame.cumulative_observation_count)} />
            <Stat label="Peak FRP so far" value={`${fmtNum(frame.cumulative_peak_frp, 0)} MW`} />
            <Stat label="Footprint" value={`${fmtNum(frame.footprint_radius_km, 2)} km`} />
            <Stat label="Deviation" value={`${fmtNum(frame.deviation_score, 0)}/100`} />
            <Stat label="Risk" value={String(Math.round(frame.risk_score))} />
          </div>
          <div className="flex items-center justify-between rounded border border-base-700 bg-base-800/60 px-2.5 py-1.5">
            <span className="font-mono text-xs text-base-200">{fmtDate(frame.observation.timestamp)}</span>
            <RiskBadge severity={frame.severity} score={frame.risk_score} size="sm" />
          </div>
          {partial && <p className="font-mono text-[11px] text-base-400">risk so far: {riskSoFar.join(" → ")}</p>}
        </div>
      </div>

      <div>
        <div className="h-1 w-full overflow-hidden rounded bg-base-700">
          <div className="h-full bg-accent transition-all" style={{ width: `${frames.length <= 1 ? 100 : (idx / (frames.length - 1)) * 100}%` }} />
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <button onClick={() => { setPlaying(false); setStep(0); }} className={BTN} aria-label="Restart" title="Restart">⏮</button>
          <button onClick={() => { setPlaying(false); setStep((s) => Math.max(0, s - 1)); }} disabled={idx === 0} className={BTN} aria-label="Step back" title="Step back">◀</button>
          <button
            onClick={() => { if (!playing && idx >= frames.length - 1) setStep(0); setPlaying((p) => !p); }}
            className="btn px-5"
          >
            {playing ? "Pause" : idx >= frames.length - 1 ? "Replay" : "Play"}
          </button>
          <button onClick={() => { setPlaying(false); setStep((s) => Math.min(s + 1, frames.length - 1)); }} disabled={idx >= frames.length - 1} className={BTN} aria-label="Step forward" title="Step forward">▶</button>
          <input
            type="range" min={0} max={frames.length - 1} value={idx} aria-label="Replay position"
            onChange={(e) => { setPlaying(false); setStep(Number(e.target.value)); }}
            className="ml-2 flex-1 accent-accent"
          />
        </div>
      </div>
    </div>
  );
}
