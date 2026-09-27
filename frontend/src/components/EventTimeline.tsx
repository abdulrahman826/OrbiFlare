"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { CHART, TOOLTIP_STYLE } from "@/lib/chartTheme";
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
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: CHART.tickText }} axisLine={{ stroke: CHART.axisLine }} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: CHART.tickText }} axisLine={false} tickLine={false} width={32} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Line type="monotone" dataKey="frp" name="FRP (MW)" stroke={CHART.primary} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
