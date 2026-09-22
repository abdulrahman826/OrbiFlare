"use client";

import { useEffect, useMemo, useState } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import { fmtDate, fmtNum } from "@/lib/format";
import type { EventReplay } from "@/types/domain";

export function EventReplayPlayer({ replay }: { replay: EventReplay }) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frames = replay.frames;
  const frame = frames[Math.min(step, frames.length - 1)];

  useEffect(() => {
    if (!playing) return;
    if (step >= frames.length - 1) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setStep((s) => Math.min(s + 1, frames.length - 1)), 900);
    return () => clearTimeout(t);
  }, [playing, step, frames.length]);

  const progressPct = useMemo(() => (frames.length <= 1 ? 100 : (step / (frames.length - 1)) * 100), [step, frames.length]);

  if (!frame) return <p className="text-sm text-base-400">No observations to replay.</p>;

  return (
    <div>
      <p className="mb-3 text-[11px] text-base-500">{replay.note}</p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Step" value={`${frame.step} / ${frames.length}`} />
        <Stat label="Observations so far" value={String(frame.cumulative_observation_count)} />
        <Stat label="Peak FRP so far" value={`${fmtNum(frame.cumulative_peak_frp, 0)} MW`} />
        <Stat label="Footprint radius" value={`${fmtNum(frame.footprint_radius_km, 2)} km`} />
      </div>

      <div className="mt-3 flex items-center justify-between rounded border border-base-700 bg-base-800 px-3 py-2">
        <div className="text-xs text-base-300">{fmtDate(frame.observation.timestamp)}</div>
        <RiskBadge severity={frame.severity} score={frame.risk_score} size="sm" />
      </div>

      <div className="mt-4">
        <div className="h-1.5 w-full overflow-hidden rounded bg-base-700">
          <div className="h-full bg-accent transition-all" style={{ width: `${progressPct}%` }} />
        </div>
        <div className="mt-3 flex items-center gap-2">
          <button onClick={() => setStep(0)} className="rounded border border-base-600 px-2.5 py-1.5 text-xs text-base-300 hover:border-accent/50">
            {"⏮"}
          </button>
          <button
            onClick={() => setPlaying((p) => !p)}
            className="rounded border border-accent/50 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            {playing ? "Pause" : step >= frames.length - 1 ? "Replay" : "Play Event"}
          </button>
          <button
            onClick={() => setStep((s) => Math.min(s + 1, frames.length - 1))}
            className="rounded border border-base-600 px-2.5 py-1.5 text-xs text-base-300 hover:border-accent/50"
          >
            {"⏭"}
          </button>
          <input
            type="range"
            min={0}
            max={frames.length - 1}
            value={step}
            onChange={(e) => {
              setPlaying(false);
              setStep(Number(e.target.value));
            }}
            className="ml-2 flex-1 accent-accent"
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-base-700 bg-base-800 px-2.5 py-2">
      <div className="text-[10px] uppercase text-base-400">{label}</div>
      <div className="font-mono text-sm text-base-100">{value}</div>
    </div>
  );
}
