"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import type { ThermalObservation } from "@/types/domain";

export function EventTimeline({ observations }: { observations: ThermalObservation[] }) {
  const data = [...observations]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((o) => ({
      time: new Date(o.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
      frp: o.frp,
      bt: o.brightness_temperature,
    }));

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: -10, right: 10, top: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DAD3C2" vertical={false} />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#6C7065" }} axisLine={{ stroke: "#C2BAA5" }} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: "#6C7065" }} axisLine={false} tickLine={false} width={32} />
          <Tooltip contentStyle={{ background: "#FBF9F3", border: "1px solid #C2BAA5", fontSize: 11 }} />
          <Line type="monotone" dataKey="frp" name="FRP (MW)" stroke="#2F4A3A" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
