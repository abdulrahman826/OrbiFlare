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

function NoPattern({ title }: { title: string }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-base-400">{title}</div>
      <p className="text-xs text-base-400">Insufficient history — no pattern is asserted.</p>
    </div>
  );
}

function PatternChart({ title, data, xKey, labelFmt, interval }: { title: string; data: Record<string, number>[]; xKey: string; labelFmt: (v: number) => string; interval: number }) {
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-base-400">{title}</div>
      <div className="h-32 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: -20, right: 4, top: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#DAD3C2" vertical={false} />
            <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: "#6C7065" }} interval={interval} axisLine={{ stroke: "#C2BAA5" }} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: "#6C7065" }} axisLine={false} tickLine={false} width={28} unit="%" />
            <Tooltip
              contentStyle={{ background: "#FBF9F3", border: "1px solid #C2BAA5", fontSize: 11 }}
              labelFormatter={(v) => labelFmt(Number(v))}
              formatter={(v: number) => [`${v}%`, "of historical observations"]}
            />
            <Bar dataKey="freq" fill="#3F5B4A" radius={[2, 2, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function FacilityThermalProfile({ twin }: { twin: ThermalTwin }) {
  const hourData = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    freq: Math.round((twin.normal_hour_pattern[String(h)] || 0) * 100),
  }));

  const monthData = Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    freq: Math.round((twin.normal_seasonal_pattern[String(i + 1)] || 0) * 100),
  }));
  const hasHours = hourData.some((d) => d.freq > 0);
  const hasMonths = monthData.some((d) => d.freq > 0);

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

      {hasHours ? <PatternChart title="Hour-of-day activity pattern (UTC)" data={hourData} xKey="hour" labelFmt={(h) => `${h}:00 UTC`} interval={2} /> : <NoPattern title="Hour-of-day activity pattern" />}
      {hasMonths ? <PatternChart title="Seasonal pattern (month of year)" data={monthData} xKey="month" labelFmt={(m) => `Month ${m}`} interval={0} /> : <NoPattern title="Seasonal pattern" />}

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
