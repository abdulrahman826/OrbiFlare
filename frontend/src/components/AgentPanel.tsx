"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { HistoricalBadge } from "@/components/DemoBadge";
import { RiskBadge } from "@/components/RiskBadge";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import type { AgentResponse, AgentResultCard, Severity, TrajectoryDirection } from "@/types/domain";

interface Entry {
  query: string;
  response?: AgentResponse;
  error?: string;
}

type Data = Record<string, unknown>;

function EventResult({ card }: { card: AgentResultCard }) {
  const d = card.data as Data;
  const id = String(d.event_id ?? card.title);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-base-700 bg-base-800/50 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <RiskBadge severity={(d.severity as Severity) ?? null} score={(d.risk_score as number) ?? null} size="sm" />
        <span className="font-mono text-xs text-base-100">{id}</span>
        <TrajectoryBadge direction={(d.trajectory_direction as TrajectoryDirection) ?? null} />
        <span className="font-mono text-[11px] text-base-400">
          FRP {fmtNum(d.peak_frp as number, 0)} MW · {String(d.observation_count ?? "?")} obs · dev {d.baseline_confidence === "INSUFFICIENT" ? "insufficient" : d.baseline_confidence == null ? "no baseline" : d.overall_deviation_score != null ? `${fmtNum(d.overall_deviation_score as number, 0)}/100` : "n/a"}
        </span>
        <span className="rounded border border-base-600 px-1 font-mono text-[9px] text-base-400">{d.is_demo ? "DEMO" : "LIVE"}</span>
      </div>
      <Link href={`/investigation/${id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Investigate →</Link>
    </div>
  );
}

function IncidentResult({ card }: { card: AgentResultCard }) {
  const d = card.data as Data;
  const id = String(d.incident_id ?? card.title);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-base-700 bg-base-800/50 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <HistoricalBadge compact />
        <span className="font-mono text-xs text-base-100">{id}</span>
        <span className="text-xs text-base-100">{String(d.name ?? "")}</span>
        <span className="font-mono text-[11px] text-base-400">{String(d.date ?? "")} · {String(d.state ?? "")}{d.distance_km != null ? ` · ${String(d.distance_km)} km away` : ""}</span>
      </div>
      <Link href={`/incidents/${id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Context →</Link>
    </div>
  );
}

function GenericResult({ card }: { card: AgentResultCard }) {
  const d = card.data as Data;
  const rows = Object.entries(d).filter(([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v)).slice(0, 12);
  return (
    <div className="rounded border border-base-700 bg-base-800/50 px-2.5 py-2">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-base-300">{card.title}</div>
      <dl className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-base-700/40 py-0.5 text-[11px]">
            <dt className="text-base-400">{k.replace(/_/g, " ")}</dt>
            <dd className="font-mono text-base-100">{v === null ? "—" : typeof v === "number" ? fmtNum(v, 2) : String(v)}</dd>
          </div>
        ))}
      </dl>
      {rows.length === 0 && <pre className="scrollbar-thin max-h-40 overflow-auto text-[10px] text-base-300">{JSON.stringify(d, null, 1)}</pre>}
    </div>
  );
}

export function AgentPanel({ suggestions }: { suggestions: string[] }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function run(query: string) {
    const q = query.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    try {
      const response = await api.agentQuery(q);
      setEntries((e) => [{ query: q, response }, ...e]);
    } catch (err) {
      setEntries((e) => [{ query: q, error: err instanceof Error ? err.message : "Backend unreachable" }, ...e]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={(e) => { e.preventDefault(); void run(input); }} className="flex gap-2" role="search">
        <span className="flex items-center text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Query</span>
        <input
          ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} aria-label="Query"
          placeholder="Query events, facilities, risk, baselines…  e.g. “show escalating events”"
          className="flex-1 rounded border border-base-600 bg-base-900 px-3 py-2 font-mono text-sm text-base-100 placeholder:text-base-500 focus:border-accent focus:outline-none"
        />
        <button type="submit" disabled={busy || !input.trim()} className="btn px-4 py-2">
          {busy ? "Running" : "Run"}
        </button>
      </form>

      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button key={s} onClick={() => void run(s)} disabled={busy} className="rounded border border-base-600 px-2 py-1 font-mono text-[11px] text-base-300 hover:border-accent/60 hover:text-accent disabled:opacity-50">
            {s}
          </button>
        ))}
      </div>

      {entries.length === 0 && (
        <div className="rounded border border-dashed border-base-600 px-3 py-6 text-center text-xs text-base-400">
          No queries run yet. Every result is assembled from the read-only tool registry against stored data (deterministic; no language model).
        </div>
      )}

      {entries.map((en, i) => (
        <article key={`${en.query}-${entries.length - i}`} className="rounded border border-base-700 bg-base-850">
          <header className="flex items-center gap-2 border-b border-base-700 px-3 py-1.5">
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Query</span>
            <span className="font-mono text-xs text-base-100">{en.query}</span>
          </header>
          <div className="space-y-2 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-base-400">Result</div>
            {en.error && <p className="text-xs text-sev-critical">Could not reach the intelligence layer: {en.error}</p>}
            {en.response && (
              <>
                <p className="text-sm leading-relaxed text-base-100">{en.response.text}</p>
                {en.response.result_cards.map((c, ci) => (c.type === "event" ? <EventResult key={ci} card={c} /> : c.type === "incident" ? <IncidentResult key={ci} card={c} /> : <GenericResult key={ci} card={c} />))}
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-base-700/60 pt-2">
                  <span className="font-mono text-[10px] text-base-500">
                    source · read-only tools: {en.response.tool_calls.length ? en.response.tool_calls.map((t) => `${t.tool} (${t.result_summary})`).join(", ") : "none"}
                  </span>
                  <span className="flex gap-3">
                    {en.response.ui_action?.action === "open_investigation" && en.response.ui_action.target_id && (
                      <Link href={`/investigation/${en.response.ui_action.target_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Open investigation →</Link>
                    )}
                    {en.response.ui_action?.action === "open_incident" && en.response.ui_action.target_id && (
                      <Link href={`/incidents/${en.response.ui_action.target_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Open historical record →</Link>
                    )}
                    {en.response.ui_action?.action === "open_facility" && en.response.ui_action.target_id && (
                      <>
                        <Link href={`/facilities/${en.response.ui_action.target_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Facility →</Link>
                        <Link href={`/thermal-twins/${en.response.ui_action.target_id}`} className="text-[11px] font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Thermal Twin →</Link>
                      </>
                    )}
                  </span>
                </div>
              </>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
