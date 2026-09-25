"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/components/Icon";
import { cn } from "@/lib/cn";
import { DATA_MODE_UI } from "@/lib/format";

const NAV_ITEMS: { href: string; label: string; icon: IconName }[] = [
  { href: "/command-center", label: "Command Center", icon: "command" },
  { href: "/events", label: "Events", icon: "events" },
  { href: "/replay", label: "Event Replay", icon: "replay" },
  { href: "/facilities", label: "Facilities", icon: "facilities" },
  { href: "/thermal-twins", label: "Thermal Twins", icon: "twins" },
  { href: "/gis", label: "GIS Explorer", icon: "gis" },
  { href: "/analytics", label: "Analytics", icon: "analytics" },
  { href: "/reports", label: "Reports", icon: "reports" },
  { href: "/model", label: "Model", icon: "model" },
  { href: "/agent", label: "Query Console", icon: "agent" },
  { href: "/limitations", label: "Limitations", icon: "limitations" },
];

export function currentPageLabel(pathname: string | null): string {
  const hit = NAV_ITEMS.find((i) => pathname?.startsWith(i.href));
  if (hit) return hit.label;
  if (pathname?.startsWith("/investigation")) return "Investigation";
  if (pathname?.startsWith("/incidents")) return "Historical Reference";
  return "";
}

export interface SidebarStatus {
  dataMode: string;
  backendOk: boolean;
  database: string;
  lastUpdated: string;
}

export function Sidebar({ status }: { status: SidebarStatus }) {
  const pathname = usePathname();
  const ui = DATA_MODE_UI[status.dataMode] ?? DATA_MODE_UI.EMPTY;
  return (
    <aside className="sticky top-0 flex h-screen w-[210px] shrink-0 flex-col border-r border-base-600 bg-base-900">
      <Link href="/command-center" className="block border-b border-base-600 px-4 py-3.5">
        <div className="text-[15px] font-bold tracking-[0.14em] text-base-100">ORBIFLARE</div>
        <div className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-base-400">Industrial Thermal Intelligence</div>
      </Link>

      <nav aria-label="Primary" className="scrollbar-thin min-h-0 flex-1 overflow-y-auto py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href) || (item.href === "/events" && pathname?.startsWith("/investigation")) || (item.href === "/gis" && pathname?.startsWith("/incidents"));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 px-4 py-2 text-[13px] transition-colors",
                active ? "bg-base-100 font-semibold text-base-850" : "text-base-200 hover:bg-base-700/60"
              )}
            >
              <Icon name={item.icon} size={15} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <dl className="space-y-1.5 border-t border-base-600 px-4 py-3 text-[11px]">
        <dt className="text-[10px] font-semibold uppercase tracking-[0.1em] text-base-400">Data status</dt>
        <dd className="flex items-center justify-between"><span className="text-base-300">Mode</span><span className={cn("rounded border px-1.5 py-px font-mono text-[10px] font-semibold", ui.tone)}>{ui.short}</span></dd>
        <dd className="flex items-center justify-between">
          <span className="text-base-300">System</span>
          <span className={cn("flex items-center gap-1.5 font-mono", status.backendOk ? "text-sev-low" : "text-sev-critical")}>
            <span className={cn("h-1.5 w-1.5", status.backendOk ? "bg-sev-low" : "bg-sev-critical")} />
            {status.backendOk ? `OK · ${status.database}` : "DOWN"}
          </span>
        </dd>
        <dd className="flex items-center justify-between"><span className="text-base-300">Last sync</span><span className="font-mono text-base-200">{status.lastUpdated}</span></dd>
        <dd className="pt-1 text-[10px] leading-snug text-base-400">Thermal detections are observations, not confirmed fires.</dd>
      </dl>
    </aside>
  );
}
