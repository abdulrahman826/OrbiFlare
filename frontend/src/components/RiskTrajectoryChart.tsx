"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import { CHART, TOOLTIP_STYLE } from "@/lib/chartTheme";
import type { RiskTrajectory } from "@/types/domain";

export function RiskTrajectoryChart({ trajectory }: { trajectory: RiskTrajectory }) {
  const data = trajectory.points.map((p, i) => ({
    step: i + 1,
    risk: p.risk_score,
    time: new Date(p.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  }));
  // Terracotta is reserved for things that deserve attention -- an escalating trajectory is exactly that. Any other direction
  // (increasing/stable/decreasing/insufficient data) keeps the routine desert tone. This only recolours the line; the
  // direction itself is still whatever the backend computed.
  const lineColor = trajectory.direction === "ESCALATING" ? CHART.secondary : CHART.primary;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-base-300">{data.map((d) => Math.round(d.risk)).join(" → ")}</span>
        <TrajectoryBadge direction={trajectory.direction} />
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ left: -20, right: 8, top: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={lineColor} stopOpacity={0.22} />
                <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: CHART.tickText }} axisLine={{ stroke: CHART.axisLine }} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: CHART.tickText }} axisLine={false} tickLine={false} width={28} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Area type="monotone" dataKey="risk" stroke={lineColor} strokeWidth={2} fill="url(#riskFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[11px] text-base-500">
        Risk trajectory reflects observed data only; it does not predict future fire behaviour.
      </p>
    </div>
  );
}
