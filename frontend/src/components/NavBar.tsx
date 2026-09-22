"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const NAV_ITEMS = [
  { href: "/command-center", label: "Command Center" },
  { href: "/events", label: "Events" },
  { href: "/replay", label: "Event Replay" },
  { href: "/facilities", label: "Facilities" },
  { href: "/thermal-twins", label: "Thermal Twins" },
  { href: "/gis", label: "GIS Explorer" },
  { href: "/analytics", label: "Analytics" },
  { href: "/reports", label: "Reports" },
  { href: "/model", label: "Model" },
  { href: "/agent", label: "Agent" },
  { href: "/limitations", label: "Limitations" },
];

export function NavBar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-base-700 bg-base-900/95 backdrop-blur">
      <div className="flex items-center gap-6 px-4">
        <Link href="/command-center" className="flex shrink-0 items-center gap-2 py-3">
          <span className="inline-block h-2 w-2 rounded-full bg-accent shadow-[0_0_8px_2px_rgba(63,208,224,0.6)]" />
          <span className="font-mono text-sm font-bold tracking-wider text-base-100">ORBIFLARE</span>
        </Link>
        <nav className="scrollbar-thin flex flex-1 gap-1 overflow-x-auto py-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "whitespace-nowrap rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                  active ? "bg-accent/10 text-accent" : "text-base-300 hover:bg-base-800 hover:text-base-100"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
