import type { ReactNode } from "react";
import { Panel } from "@/components/Panel";

export function ChartCard({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <Panel title={title}>
      {children}
      {note && <p className="mt-2 text-[11px] text-base-500">{note}</p>}
    </Panel>
  );
}
