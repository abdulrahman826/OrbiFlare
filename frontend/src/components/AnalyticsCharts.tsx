"use client";

import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ChartCard";

const SEVERITY_COLORS: Record<string, string> = { LOW: "#4a9a6a", MEDIUM: "#c9a227", HIGH: "#d97b3f", CRITICAL: "#d1453f" };
const TOOLTIP_STYLE = { background: "#12151b", border: "1px solid #2a3038", fontSize: 11 };

function toChartData(obj: Record<string, number>) {
  return Object.entries(obj).map(([name, value]) => ({ name, value }));
}

// `colorMode` is a serializable enum rather than a function prop -- Server
// Components can't pass functions to Client Components as props.
type ColorMode = "default" | "classification";

function colorForMode(mode: ColorMode | undefined, key: string): string {
  if (mode === "classification") return key.startsWith("PERSISTENT") ? "#3fd0e0" : "#c9a227";
  return "#3fd0e0";
}

export function BarByKey({ title, data, colorMode, note }: { title: string; data: Record<string, number>; colorMode?: ColorMode; note?: string }) {
  const chartData = toChartData(data);
  return (
    <ChartCard title={title} note={note}>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ left: -20, right: 10, top: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f242c" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={{ stroke: "#2a3038" }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={false} tickLine={false} width={30} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={colorForMode(colorMode, d.name)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

export function SeverityPie({ data }: { data: Record<string, number> }) {
  const chartData = toChartData(data);
  return (
    <ChartCard title="Events by Severity">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={SEVERITY_COLORS[d.name] || "#5a6169"} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

export function DeviationHistogram({ values }: { values: number[] }) {
  const buckets = [0, 20, 40, 60, 80, 100];
  const counts = buckets.slice(0, -1).map((b, i) => ({
    name: `${b}-${buckets[i + 1]}`,
    value: values.filter((v) => v >= b && v < buckets[i + 1]).length,
  }));
  return (
    <ChartCard title="Deviation Score Distribution" note="Composite behavioural deviation (0-100) across all events">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={counts} margin={{ left: -20, right: 10, top: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f242c" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={{ stroke: "#2a3038" }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#7d848c" }} axisLine={false} tickLine={false} width={30} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="value" fill="#3fd0e0" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}
