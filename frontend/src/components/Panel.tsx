import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

/**
 * `box`     -- a flat bordered panel (maps, tables, feeds).
 * `section` -- report style: no box, a heavy rule and a heading, content flows on the page.
 */
export function Panel({
  children, className, title, action, flush = false, sub, variant = "box",
}: { children: ReactNode; className?: string; title?: string; action?: ReactNode; flush?: boolean; sub?: string; variant?: "box" | "section" }) {
  if (variant === "section") {
    return (
      <section className={cn("min-w-0 border-t-2 border-base-100 pt-2", className)}>
        {title && (
          <header className="mb-2 flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.1em] text-base-100">{title}</h2>
              {sub && <p className="mt-0.5 text-[11px] text-base-400">{sub}</p>}
            </div>
            {action}
          </header>
        )}
        <div className="min-h-0">{children}</div>
      </section>
    );
  }
  return (
    <section className={cn("flex min-w-0 flex-col rounded border border-base-600 bg-base-850", className)}>
      {title && (
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-base-600 bg-base-900/60 px-3 py-1.5">
          <div className="min-w-0">
            <h2 className="truncate text-[11px] font-bold uppercase tracking-[0.1em] text-base-100">{title}</h2>
            {sub && <p className="mt-0.5 text-[11px] font-normal normal-case tracking-normal text-base-400">{sub}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cn("min-h-0 flex-1", flush ? "" : "p-3")}>{children}</div>
    </section>
  );
}

/** Page title row used at the top of every page. */
export function PageHeader({ title, sub, action }: { title: string; sub?: string; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4 border-b border-base-600 pb-2">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight text-base-100">{title}</h1>
        {sub && <p className="mt-0.5 max-w-3xl text-xs text-base-400">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

/** Label / value row for dense key-value lists. */
export function DataRow({ label, value, mono = true }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-base-700 py-1 text-xs last:border-0">
      <span className="text-base-400">{label}</span>
      <span className={cn("text-right text-base-100", mono && "font-mono")}>{value}</span>
    </div>
  );
}

/** Loading / empty / error / unavailable state block. */
export function StateBlock({ kind, title, children }: { kind: "empty" | "error" | "unavailable" | "insufficient"; title: string; children?: ReactNode }) {
  const tone = kind === "error" ? "border-sev-critical/50 text-sev-critical" : kind === "insufficient" ? "border-sev-medium/60 text-sev-medium" : "border-base-600 text-base-300";
  return (
    <div className={cn("rounded border border-dashed bg-base-850 px-3 py-4 text-center", tone)}>
      <div className="text-xs font-semibold uppercase tracking-wider">{title}</div>
      {children && <div className="mt-1 text-xs text-base-400">{children}</div>}
    </div>
  );
}
