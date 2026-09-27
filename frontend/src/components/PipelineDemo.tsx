"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * A small, self-contained, deterministic walkthrough of the OrbiFlare intelligence pipeline,
 * built for the SIH 2026 demo video. Every value shown while the sequence runs is fixed --
 * this component never calls the API, never reads real event data, and mutates nothing.
 * The only live element is the closing "Open investigation" link.
 *
 * INTENTIONALLY FROZEN: by request, this page keeps its original (pre-industrial-theme) look
 * even as the rest of the app moved to the new palette. Every colour below is a literal hex
 * value snapshotted from the old shared `base`/`accent`/`sev`/`ochre` tokens, not a reference
 * to those tokens -- so it will NOT drift if the shared theme changes again later.
 */

type StageId = "firms" | "event" | "twin" | "deviation" | "evidence" | "risk" | "orbiflare";

const STAGES: { id: StageId; index: string; title: string; kicker: string }[] = [
  { id: "firms", index: "01", title: "FIRMS", kicker: "NASA VIIRS / MODIS\nThermal observation" },
  { id: "event", index: "02", title: "Living Thermal Event", kicker: "Spatio-temporal\nevent formation" },
  { id: "twin", index: "03", title: "Facility Thermal Twin", kicker: "Historical behaviour\nnormal baseline" },
  { id: "deviation", index: "04", title: "Behaviour Deviation", kicker: "Normal → current\n→ deviation" },
  { id: "evidence", index: "05", title: "Evidence Fusion", kicker: "Thermal · temporal\nfacility · GIS · ML" },
  { id: "risk", index: "06", title: "Risk Trajectory", kicker: "Escalation over\nthe event lifetime" },
  { id: "orbiflare", index: "07", title: "OrbiFlare", kicker: "Industrial thermal\nintelligence" },
];

const STAGE_ORDER: StageId[] = STAGES.map((s) => s.id);

// Deterministic demo values -- never randomised, never fetched.
const DEMO = {
  observation: { sensor: "VIIRS", lat: "17.3852", lon: "78.4867", frp: "42.6 MW", bt: "331 K", confidence: "HIGH" },
  event: { id: "EVT-024", observations: 11, persistence: "4.2 h" },
  twin: { expectedLow: 18, expectedHigh: 25, current: 42.6 },
  deviation: [
    { label: "Intensity", level: "HIGH" as const },
    { label: "Persistence", level: "HIGH" as const },
    { label: "Temporal", level: "MEDIUM" as const },
    { label: "Spatial", level: "LOW" as const },
  ],
  evidence: ["Thermal", "Facility", "GIS", "Temporal", "ML"],
  trajectory: [29, 39, 57, 74],
  finalRisk: 74,
};

// Timing for the automated run (ms), stage-by-stage. Totals ~9.5s -- inside the requested 8-12s.
const STAGE_DELAY_MS: Record<StageId, number> = {
  firms: 700, event: 1300, twin: 1300, deviation: 1500, evidence: 1700, risk: 1700, orbiflare: 900,
};

function levelTone(level: "LOW" | "MEDIUM" | "HIGH") {
  return level === "HIGH"
    ? "text-[#B4530F] border-[#B4530F]/50 bg-[#B4530F]/10"
    : level === "MEDIUM"
      ? "text-[#8A6A1E] border-[#8A6A1E]/50 bg-[#8A6A1E]/10"
      : "text-[#6C7065] border-[#C2BAA5] bg-[#EDE8DA]/40";
}

export function PipelineDemo({ flagshipEventId }: { flagshipEventId: string | null }) {
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [reached, setReached] = useState<Set<StageId>>(new Set());
  const [active, setActive] = useState<StageId | null>(null);
  const [packetAt, setPacketAt] = useState<number>(-1); // index of stage the packet is currently travelling toward
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const runSequence = useCallback(() => {
    clearTimers();
    setRunning(true);
    setDone(false);
    setReached(new Set());
    setActive(null);
    setPacketAt(-1);
    let t = 0;
    STAGE_ORDER.forEach((stage, i) => {
      t += STAGE_DELAY_MS[stage];
      timers.current.push(
        setTimeout(() => {
          setPacketAt(i);
          setActive(stage);
          setReached((prev) => new Set(prev).add(stage));
          if (stage === "orbiflare") {
            setRunning(false);
            setDone(true);
          }
        }, t),
      );
    });
  }, [clearTimers]);

  const showStage = useCallback((stage: StageId) => {
    const i = STAGE_ORDER.indexOf(stage);
    setActive(stage);
    setPacketAt(i);
    setReached((prev) => {
      // Manual inspection reveals a stage without pretending earlier stages ran -- but never hides progress already made automatically.
      const next = new Set(prev);
      next.add(stage);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    clearTimers();
    setRunning(false);
    setDone(false);
    setReached(new Set());
    setActive(null);
    setPacketAt(-1);
  }, [clearTimers]);

  const activeStage = active ?? "firms";
  const trajectoryShown = useMemo(() => {
    if (!reached.has("risk") && active !== "risk") return [] as number[];
    return DEMO.trajectory;
  }, [reached, active]);

  return (
    <div className="flex h-[calc(100vh-7.5rem)] min-h-[560px] flex-col gap-3">
      <PipelineHeader running={running} done={done} />
      <IncomingObservation onRun={runSequence} onReset={reset} running={running} done={done} />

      <PacketTrack packetAt={packetAt} stageCount={STAGES.length} />
      <div className="relative flex min-w-0 flex-1 items-stretch gap-0">
        {STAGES.map((stage, i) => (
          <StageCard
            key={stage.id}
            stage={stage}
            index={i}
            isActive={activeStage === stage.id}
            isReached={reached.has(stage.id)}
            onClick={() => showStage(stage.id)}
          />
        ))}
      </div>

      <BottomStrip flagshipEventId={flagshipEventId} done={done} trajectoryLen={trajectoryShown.length} />
    </div>
  );
}

function PipelineHeader({ running, done }: { running: boolean; done: boolean }) {
  const statusLabel = done ? "INVESTIGATION READY" : running ? "PIPELINE RUNNING" : "SIMULATION / PIPELINE READY";
  const dotClass = done ? "bg-[#2F4A3A]" : running ? "bg-[#8A6A1E]" : "bg-[#A39C88]";
  return (
    <div className="flex items-end justify-between gap-4 border-b border-[#C2BAA5] pb-2">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight text-[#1F2421]">ORBIFLARE // INTELLIGENCE PIPELINE</h1>
        <p className="mt-0.5 text-xs text-[#6C7065]">From raw thermal observations to explainable risk intelligence</p>
      </div>
      <div className="flex items-center gap-1.5 rounded border border-[#C2BAA5] bg-[#FBF9F3] px-2.5 py-1">
        <span className={cn("h-1.5 w-1.5 rounded-full", dotClass, running && "animate-pulse")} />
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#54584E]">{statusLabel}</span>
      </div>
    </div>
  );
}

function IncomingObservation({ onRun, onReset, running, done }: { onRun: () => void; onReset: () => void; running: boolean; done: boolean }) {
  const o = DEMO.observation;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#C2BAA5] bg-[#FBF9F3] px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6C7065]">Incoming observation</span>
        <DataChip label="Sensor" value={o.sensor} />
        <DataChip label="Lat" value={o.lat} />
        <DataChip label="Lon" value={o.lon} />
        <DataChip label="FRP" value={o.frp} />
        <DataChip label="BT" value={o.bt} />
        <DataChip label="Confidence" value={o.confidence} tone="text-[#2F4A3A]" />
      </div>
      <div className="flex items-center gap-2">
        {(running || done) && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center justify-center whitespace-nowrap rounded border border-[#C2BAA5] bg-[#FBF9F3] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#1F2421] transition-colors hover:bg-[#F0EBDF] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Reset
          </button>
        )}
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          className="inline-flex items-center justify-center whitespace-nowrap rounded bg-[#2F4A3A] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#FBF9F3] transition-colors hover:bg-[#3F6350] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? "Running…" : done ? "▶ Run again" : "▶ Run intelligence"}
        </button>
      </div>
    </div>
  );
}

function DataChip({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="font-mono text-[11px] text-[#1F2421]">
      <span className="text-[#6C7065]">{label} </span>
      <span className={tone}>{value}</span>
    </span>
  );
}

function PacketTrack({ packetAt, stageCount }: { packetAt: number; stageCount: number }) {
  const pct = packetAt < 0 ? 100 / (stageCount * 2) : ((packetAt + 0.5) / stageCount) * 100;
  return (
    <div className="relative h-1 shrink-0 overflow-visible rounded-full bg-[#DAD3C2]" aria-hidden>
      <div className="h-full rounded-full bg-[#2F4A3A]/60 transition-[width] duration-700 ease-out" style={{ width: `${pct}%` }} />
      <div
        className="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-[#8A6A1E] shadow-[0_0_6px_1px_rgba(138,106,30,0.55)] transition-[left] duration-700 ease-out"
        style={{ left: `${pct}%`, transform: "translate(-50%, -50%)" }}
      />
    </div>
  );
}

function StageCard({
  stage, index, isActive, isReached, onClick,
}: {
  stage: (typeof STAGES)[number]; index: number; isActive: boolean; isReached: boolean; onClick: () => void;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-stretch">
      <button
        type="button"
        onClick={onClick}
        data-testid={`stage-${stage.id}`}
        data-active={isActive}
        data-reached={isReached}
        className={cn(
          "relative flex min-w-0 flex-1 flex-col overflow-hidden rounded border bg-[#FBF9F3] p-3 text-left transition-all duration-500",
          isActive ? "border-[#8A6A1E] shadow-[0_0_0_1px_rgba(138,106,30,0.35)]" : isReached ? "border-[#2F4A3A]/50" : "border-[#C2BAA5]",
        )}
      >
        <span aria-hidden className="pointer-events-none absolute -right-2 -top-4 select-none font-mono text-[64px] font-bold leading-none text-[#EDE8DA]/[0.06]">
          {stage.index}
        </span>
        <span className="font-mono text-[10px] text-[#6C7065]">{stage.index}</span>
        <div className="flex flex-1 flex-col justify-center gap-2 py-2">
          <div>
            <span className={cn("text-[14px] font-bold uppercase leading-tight tracking-[0.04em]", isActive || isReached ? "text-[#1F2421]" : "text-[#54584E]")}>
              {stage.title}
            </span>
            <span className="mt-1 block whitespace-pre-line text-[10.5px] leading-snug text-[#6C7065]">{stage.kicker}</span>
          </div>
          <StageBody stage={stage.id} isActive={isActive} isReached={isReached} />
        </div>
      </button>
      {index < STAGES.length - 1 && (
        <div className="flex w-4 shrink-0 items-center justify-center">
          <span className={cn("text-[14px] transition-colors duration-500", isReached ? "text-[#2F4A3A]" : "text-[#C2BAA5]")}>&rarr;</span>
        </div>
      )}
    </div>
  );
}

function StageBody({ stage, isActive, isReached }: { stage: StageId; isActive: boolean; isReached: boolean }) {
  const shown = isActive || isReached;
  if (stage === "firms") {
    return (
      <div className={cn("transition-opacity duration-500", shown ? "opacity-100" : "opacity-40")}>
        <div className="font-mono text-[12px] text-[#54584E]">{DEMO.observation.sensor} · {DEMO.observation.frp}</div>
        <div className="mt-0.5 font-mono text-[11px] text-[#6C7065]">{DEMO.observation.lat}, {DEMO.observation.lon}</div>
      </div>
    );
  }
  if (stage === "event") {
    return (
      <div className={cn("transition-opacity duration-500", shown ? "opacity-100" : "opacity-0")}>
        <div className="font-mono text-[13px] font-semibold text-[#1F2421]">{DEMO.event.id}</div>
        <div className="mt-0.5 text-[11px] text-[#6C7065]">{DEMO.event.observations} observations · persistence {DEMO.event.persistence}</div>
      </div>
    );
  }
  if (stage === "twin") {
    const pct = Math.min(100, (DEMO.twin.current / (DEMO.twin.expectedHigh * 2)) * 100);
    const basePct = (DEMO.twin.expectedHigh / (DEMO.twin.expectedHigh * 2)) * 100;
    return (
      <div className={cn("space-y-1.5 transition-opacity duration-500", shown ? "opacity-100" : "opacity-0")}>
        <div className="text-[11px] text-[#6C7065]">Expected FRP <span className="font-mono text-[#30342F]">{DEMO.twin.expectedLow}&ndash;{DEMO.twin.expectedHigh} MW</span></div>
        <div className="text-[11px] text-[#6C7065]">Current FRP <span className="font-mono font-semibold text-[#B4530F]">{DEMO.twin.current} MW</span></div>
        <div className="relative mt-1 h-1.5 rounded-full bg-[#DAD3C2]">
          <span className="absolute inset-y-0 left-0 w-px bg-[#6C7065]" style={{ left: `${basePct}%` }} aria-hidden />
          <div className={cn("h-full rounded-full bg-[#B4530F] transition-all duration-700", shown ? "" : "w-0")} style={{ width: shown ? `${pct}%` : 0 }} />
        </div>
      </div>
    );
  }
  if (stage === "deviation") {
    return (
      <div className={cn("flex flex-wrap gap-1.5 transition-opacity duration-500", shown ? "opacity-100" : "opacity-0")}>
        {DEMO.deviation.map((d) => (
          <span key={d.label} className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase leading-none", levelTone(d.level))}>
            {d.label} {d.level}
          </span>
        ))}
      </div>
    );
  }
  if (stage === "evidence") {
    return (
      <div className="flex flex-wrap gap-1.5">
        {DEMO.evidence.map((e, i) => (
          <span
            key={e}
            className={cn(
              "rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase leading-none transition-all duration-300",
              shown ? "border-[#2F4A3A]/50 text-[#2F4A3A] opacity-100" : "border-[#C2BAA5] text-[#A39C88] opacity-40",
            )}
            style={{ transitionDelay: shown ? `${i * 140}ms` : "0ms" }}
          >
            {e} {shown ? "✓" : ""}
          </span>
        ))}
      </div>
    );
  }
  if (stage === "risk") {
    const seq = shown ? DEMO.trajectory : [];
    const max = Math.max(...DEMO.trajectory);
    return (
      <div className={cn("transition-opacity duration-500", shown ? "opacity-100" : "opacity-0")}>
        <div className="flex items-end gap-1.5" style={{ height: 28 }}>
          {seq.map((v, i) => (
            <div key={i} className="flex flex-1 flex-col items-center justify-end gap-0.5">
              <div
                className={cn("w-full rounded-sm transition-all duration-500", i === seq.length - 1 ? "bg-[#B4530F]" : "bg-[#A39C88]")}
                style={{ height: `${(v / max) * 100}%`, transitionDelay: `${i * 120}ms` }}
              />
            </div>
          ))}
        </div>
        <div className="mt-1 flex items-baseline gap-1 font-mono text-[12px] text-[#54584E]">
          {seq.map((v, i) => (
            <span key={i} className={cn(i === seq.length - 1 ? "font-bold text-[#B4530F]" : "text-[#6C7065]")}>
              {v}
              {i < seq.length - 1 ? " →" : ""}
            </span>
          ))}
        </div>
        {shown && <div className="mt-0.5 font-mono text-[10.5px] font-semibold uppercase tracking-wider text-[#B4530F]">HIGH · Escalating</div>}
      </div>
    );
  }
  return (
    <div className={cn("transition-opacity duration-500", shown ? "opacity-100" : "opacity-0")}>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-[#1F2421]">Industrial</div>
      <div className="text-[11px] uppercase tracking-wider text-[#6C7065]">Thermal intelligence</div>
    </div>
  );
}

function BottomStrip({ flagshipEventId, done, trajectoryLen }: { flagshipEventId: string | null; done: boolean; trajectoryLen: number }) {
  void trajectoryLen;
  const steps = ["NASA FIRMS", "Event formation", "Thermal twin", "Deviation engine", "Evidence fusion", "Risk engine", "GIS investigation"];
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#C2BAA5] bg-[#FBF9F3] px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1 font-mono text-[9.5px] uppercase tracking-wider text-[#6C7065]">
        {steps.map((s, i) => (
          <span key={s} className="flex items-center gap-1.5">
            <span>{s}</span>
            {i < steps.length - 1 && <span className="text-[#C2BAA5]">|</span>}
          </span>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden font-mono text-[9.5px] font-semibold uppercase tracking-[0.12em] text-[#6C7065] sm:inline">Read → Compare → Explain → Prioritize</span>
        {done && (
          <Link
            href={flagshipEventId ? `/investigation/${flagshipEventId}` : "/events"}
            className="inline-flex items-center justify-center whitespace-nowrap rounded bg-[#2F4A3A] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#FBF9F3] transition-colors hover:bg-[#3F6350]"
            data-testid="open-investigation"
          >
            Open investigation &rarr;
          </Link>
        )}
      </div>
    </div>
  );
}
