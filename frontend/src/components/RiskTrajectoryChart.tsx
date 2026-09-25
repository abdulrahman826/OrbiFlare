"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TrajectoryBadge } from "@/components/TrajectoryBadge";
import type { RiskTrajectory } from "@/types/domain";

export function RiskTrajectoryChart({ trajectory }: { trajectory: RiskTrajectory }) {
  const data = trajectory.points.map((p, i) => ({
    step: i + 1,
    risk: p.risk_score,
    time: new Date(p.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  }));

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
                <stop offset="0%" stopColor="#2F4A3A" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#2F4A3A" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#DAD3C2" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#6C7065" }} axisLine={{ stroke: "#C2BAA5" }} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#6C7065" }} axisLine={false} tickLine={false} width={28} />
            <Tooltip contentStyle={{ background: "#FBF9F3", border: "1px solid #C2BAA5", fontSize: 11 }} />
            <Area type="monotone" dataKey="risk" stroke="#2F4A3A" strokeWidth={2} fill="url(#riskFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[11px] text-base-500">
        Risk trajectory reflects observed data only; it does not predict future fire behaviour.
      </p>
    </div>
  );
}
