import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function Panel({ children, className, title, action }: { children: ReactNode; className?: string; title?: string; action?: ReactNode }) {
  return (
    <div className={cn("flex flex-col rounded-md border border-base-700 bg-base-850 shadow-panel", className)}>
      {title && (
        <div className="flex shrink-0 items-center justify-between border-b border-base-700 px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-base-200">{title}</h2>
          {action}
        </div>
      )}
      <div className="min-h-0 flex-1 p-4">{children}</div>
    </div>
  );
}
