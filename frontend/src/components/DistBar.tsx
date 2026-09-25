import { cn } from "@/lib/cn";

export interface DistItem {
  label: string;
  value: number;
  colorClass: string;
}

/** Horizontal count distribution. Shows label + count so colour is never the only cue. */
export function DistBars({ items, emptyText = "No data." }: { items: DistItem[]; emptyText?: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const total = items.reduce((a, i) => a + i.value, 0);
  if (total === 0) return <p className="text-xs text-base-400">{emptyText}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((i, idx) => (
        <li key={`${i.label}-${idx}`}className="grid grid-cols-[92px_1fr_34px] items-center gap-2 text-[11px]">
          <span className="truncate text-base-300">{i.label}</span>
          <span className="h-2 overflow-hidden rounded-sm bg-base-700/60">
            <span className={cn("block h-full rounded-sm", i.colorClass)} style={{ width: `${(i.value / max) * 100}%` }} />
          </span>
          <span className="text-right font-mono text-base-100">{i.value}</span>
        </li>
      ))}
    </ul>
  );
}
