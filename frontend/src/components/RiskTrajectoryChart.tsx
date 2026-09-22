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
                <stop offset="0%" stopColor="#3fd0e0" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#3fd0e0" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f242c" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={{ stroke: "#2a3038" }} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={false} tickLine={false} width={28} />
            <Tooltip contentStyle={{ background: "#12151b", border: "1px solid #2a3038", fontSize: 11 }} />
            <Area type="monotone" dataKey="risk" stroke="#3fd0e0" strokeWidth={2} fill="url(#riskFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
