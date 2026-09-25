"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { currentPageLabel } from "@/components/NavBar";
import { cn } from "@/lib/cn";
import { DATA_MODE_UI } from "@/lib/format";

export interface TopBarProps {
  dataMode: string;
  sensor: string;
  windowLabel: string;
  backendOk: boolean;
  activeEvents: number;
  lastSync: string;
  lastObs: string;
  firmsLabel: string;
  modelLabel: string;
}

function istNow(): string {
  return new Date().toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour12: false });
}

function Field({ label, children, tone }: { label: string; children: React.ReactNode; tone?: string }) {
  return (
    <div className="flex shrink-0 flex-col justify-center border-r border-base-600 px-3 py-1">
      <span className="text-[9px] font-semibold uppercase leading-none tracking-[0.1em] text-base-400">{label}</span>
      <span className={cn("mt-0.5 whitespace-nowrap font-mono text-[11px] leading-tight text-base-100", tone)}>{children}</span>
    </div>
  );
}

export function TopBar({ dataMode, sensor, windowLabel, backendOk, activeEvents, lastSync, lastObs, firmsLabel, modelLabel }: TopBarProps) {
  const pathname = usePathname();
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    setNow(istNow());
    const t = setInterval(() => setNow(istNow()), 1000);
    return () => clearInterval(t);
  }, []);
  const ui = DATA_MODE_UI[dataMode] ?? DATA_MODE_UI.EMPTY;
  return (
    <div className="scrollbar-thin sticky top-0 z-30 flex items-stretch overflow-x-auto border-b border-base-600 bg-base-900">
      <Field label="Data mode" tone={dataMode === "LIVE_FIRMS" ? "text-sev-low" : undefined}>{ui.top}</Field>
      <Field label="System" tone={backendOk ? "text-sev-low" : "text-sev-critical"}>{backendOk ? "OPERATIONAL" : "DEGRADED"}</Field>
      <Field label="FIRMS" tone={firmsLabel === "LAST SYNC FAILED" ? "text-sev-critical" : undefined}>{firmsLabel}</Field>
      <Field label="Last sync">{lastSync}</Field>
      <Field label="Last obs. (UTC)">{lastObs}</Field>
      <Field label="Active events">{activeEvents}</Field>
      <Field label="Model">{modelLabel}</Field>
      <Field label="Sensor">{sensor}</Field>
      <Field label="Time (IST)">{now || "--:--:--"}</Field>
      <div className="flex items-center px-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-base-200">{currentPageLabel(pathname)}</div>
    </div>
  );
}
