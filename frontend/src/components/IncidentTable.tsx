"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { HistoricalBadge } from "@/components/DemoBadge";
import { FilterBar, FilterSelect } from "@/components/FilterBar";
import { Panel, StateBlock } from "@/components/Panel";
import type { HistoricalIncident } from "@/types/domain";

const KIND_OPTIONS = [
  { label: "Reported industrial incident", value: "REPORTED_INDUSTRIAL_INCIDENT" },
  { label: "Persistent / flare thermal source", value: "PERSISTENT_THERMAL_SOURCE_REFERENCE" },
  { label: "Agricultural burning reference", value: "AGRICULTURAL_BURNING_REFERENCE" },
  { label: "Memorial / site reference", value: "MEMORIAL_SITE_REFERENCE" },
];

const TH = "whitespace-nowrap px-2.5 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-base-400";
const TD = "px-2.5 py-2 text-xs text-base-200";

export function IncidentTable({ incidents }: { incidents: HistoricalIncident[] }) {
  const [kind, setKind] = useState("");
  const [state, setState] = useState("");
  const states = useMemo(() => Array.from(new Set(incidents.map((i) => i.state))).sort(), [incidents]);
  const rows = incidents.filter((i) => (!kind || i.record_kind === kind) && (!state || i.state === state));

  return (
    <div className="space-y-3">
      <FilterBar>
        <FilterSelect label="Kind" value={kind} onChange={setKind} options={KIND_OPTIONS} />
        <FilterSelect label="State" value={state} onChange={setState} options={states.map((s) => ({ label: s, value: s }))} />
        <span className="ml-auto font-mono text-[11px] text-base-400">{rows.length} of {incidents.length}</span>
        {(kind || state) && <button onClick={() => { setKind(""); setState(""); }} className="text-xs font-semibold uppercase tracking-wider text-accent hover:text-accent-bright">Reset</button>}
      </FilterBar>
      {rows.length === 0 ? (
        <StateBlock kind="empty" title="No historical records match the filters" />
      ) : (
        <Panel flush>
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse">
              <thead className="border-b border-base-700 bg-base-900/60">
                <tr>
                  <th className={TH}>ID</th><th className={TH}>Name</th><th className={TH}>Kind</th><th className={TH}>Date</th>
                  <th className={TH}>State</th><th className={TH}>Source (as supplied)</th><th className={TH}>Verification</th><th className={TH}>Coordinates</th><th className={TH}>Status</th><th className={TH} />
                </tr>
              </thead>
              <tbody>
                {rows.map((i) => (
                  <tr key={i.incident_id} className="border-b border-base-700/50 hover:bg-base-800/70">
                    <td className={`${TD} font-mono text-base-100`}>{i.incident_id}</td>
                    <td className={`${TD} text-base-100`}>{i.name}</td>
                    <td className={TD}>{i.record_kind_label}</td>
                    <td className={`${TD} font-mono`}>{i.date}</td>
                    <td className={TD}>{i.state}</td>
                    <td className={TD}>{i.provenance.source_label}</td>
                    <td className={TD}>Not verified</td>
                    <td className={TD}>Approximate</td>
                    <td className={TD}><HistoricalBadge compact /></td>
                    <td className={TD}><Link href={`/incidents/${i.incident_id}`} className="link-action whitespace-nowrap">Context →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
