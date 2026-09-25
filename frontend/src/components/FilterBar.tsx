"use client";

export interface FilterOption {
  label: string;
  value: string;
}

export function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: FilterOption[]; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-base-400">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-base-600 bg-base-800 px-1.5 py-1 text-xs normal-case tracking-normal text-base-100 focus:border-accent focus:outline-none"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FilterBar({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded border border-base-700 bg-base-850 px-3 py-2">{children}</div>;
}
