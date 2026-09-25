import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/NavBar";
import { TopBar } from "@/components/TopBar";
import { api } from "@/lib/api";
import { formatAcquisition, formatIst } from "@/lib/firmsRefresh";

export const metadata: Metadata = {
  title: "OrbiFlare -- Industrial Thermal Intelligence",
  description: "Industrial thermal-event intelligence from satellite observations.",
};

export const dynamic = "force-dynamic";

function shortDate(iso: string): string {
  return iso.slice(0, 10);
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [health, events, risk] = await Promise.all([
    api.health().catch(() => null),
    api.listEvents().catch(() => []),
    api.analyticsRisk().catch(() => null),
  ]);
  const dataMode = health?.data_mode ?? "EMPTY";
  const times = events.flatMap((e) => [e.first_detected, e.last_detected]).sort();
  const windowLabel = times.length ? `${shortDate(times[0])} → ${shortDate(times[times.length - 1])}` : "no data";
  const sensor = health?.sensor_label ?? "no observations";
  const activeEvents = events.filter((e) => e.status !== "EXTINGUISHED").length;
  const modelLabel = risk ? `${risk.model_metrics.model_version} · ML evidence` : "unavailable";
  const firms = health?.firms ?? null;
  const lastSync = formatIst(firms?.last_sync_at);
  const lastObs = formatAcquisition(firms?.last_acquisition);
  const firmsLabel = !firms?.configured ? "NOT CONFIGURED" : firms.last_status === "FAILED" ? "LAST SYNC FAILED" : "CONFIGURED";

  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-base-950 text-base-100 antialiased">
        <div className="flex min-h-screen">
          <Sidebar status={{ dataMode, backendOk: !!health, database: health?.database ?? "n/a", lastUpdated: lastSync }} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar dataMode={dataMode} sensor={sensor} windowLabel={windowLabel} backendOk={!!health} activeEvents={activeEvents} lastSync={lastSync} lastObs={lastObs} firmsLabel={firmsLabel} modelLabel={modelLabel} />
            <main className="min-w-0 flex-1 px-5 py-4">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
