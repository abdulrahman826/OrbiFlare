"use client";

export interface Layer {
  key: string;
  label: string;
  enabled: boolean;
  color?: string;
}

export function LayerControl({ layers, onToggle }: { layers: Layer[]; onToggle: (key: string) => void }) {
  return (
    <div className="space-y-2">
      {layers.map((l) => (
        <label key={l.key} className="flex cursor-pointer items-center gap-2 text-xs text-base-200">
          <input type="checkbox" checked={l.enabled} onChange={() => onToggle(l.key)} className="accent-accent" />
          {l.color && <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: l.color }} />}
          {l.label}
        </label>
      ))}
    </div>
  );
}
