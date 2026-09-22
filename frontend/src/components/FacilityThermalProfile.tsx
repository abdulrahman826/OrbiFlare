"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtDate, fmtNum } from "@/lib/format";
import type { ThermalTwin } from "@/types/domain";

function StatRow({ label, dist, unit }: { label: string; dist: { n: number; median: number | null; q25: number | null; q75: number | null }; unit: string }) {
  return (
    <div className="flex items-center justify-between border-t border-base-700/60 py-2 text-xs">
      <span className="text-base-300">{label}</span>
      <span className="font-mono text-base-100">
        {dist.n === 0
          ? "no data"
          : `${fmtNum(dist.median, 1)} ${unit} (IQR ${fmtNum(dist.q25, 1)}–${fmtNum(dist.q75, 1)})`}
      </span>
    </div>
  );
}

export function FacilityThermalProfile({ twin }: { twin: ThermalTwin }) {
  const hourData = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    freq: Math.round((twin.normal_hour_pattern[String(h)] || 0) * 100),
  }));

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-base-300">Historical behaviour</div>
        <StatRow label="Fire Radiative Power" dist={twin.normal_frp} unit="MW" />
        <StatRow label="Brightness temperature" dist={twin.normal_bt} unit="K" />
        <StatRow label="Persistence" dist={twin.normal_persistence} unit="obs" />
        <StatRow label="Duration" dist={twin.normal_duration} unit="h" />
        <div className="flex items-center justify-between border-t border-base-700/60 py-2 text-xs">
          <span className="text-base-300">Recurrence interval</span>
          <span className="font-mono text-base-100">{twin.normal_recurrence_days ? `~${fmtNum(twin.normal_recurrence_days, 0)} days` : "insufficient data"}</span>
        </div>
        <div className="flex items-center justify-between border-t border-base-700/60 py-2 text-xs">
          <span className="text-base-300">History span</span>
          <span className="font-mono text-base-100">
            {twin.history_start ? `${fmtDate(twin.history_start)} → ${fmtDate(twin.history_end)}` : "--"}
          </span>
        </div>
        <div className="flex items-center justify-between border-t border-base-700/60 py-2 text-xs">
          <span className="text-base-300">Normal spatial footprint radius</span>
          <span className="font-mono text-base-100">{twin.normal_spatial_radius_km !== null ? `~${fmtNum(twin.normal_spatial_radius_km, 2)} km` : "--"}</span>
        </div>
      </div>

      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-base-300">Hour-of-day activity pattern</div>
        <div className="h-32 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourData} margin={{ left: -20, right: 4, top: 4, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f242c" vertical={false} />
              <XAxis dataKey="hour" tick={{ fontSize: 9, fill: "#7d848c" }} interval={2} axisLine={{ stroke: "#2a3038" }} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: "#7d848c" }} axisLine={false} tickLine={false} width={28} />
              <Tooltip
                contentStyle={{ background: "#12151b", border: "1px solid #2a3038", fontSize: 11 }}
                labelFormatter={(h) => `${h}:00 UTC`}
                formatter={(v: number) => [`${v}%`, "of historical observations"]}
              />
              <Bar dataKey="freq" fill="#3fd0e0" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {Object.keys(twin.normal_day_night_pattern).length > 0 && (
        <div className="flex gap-4 text-xs">
          {Object.entries(twin.normal_day_night_pattern).map(([k, v]) => (
            <span key={k} className="text-base-300">
              {k === "N" ? "Night" : "Day"}: <b className="font-mono text-base-100">{Math.round(v * 100)}%</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
