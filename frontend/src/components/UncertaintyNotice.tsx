export function UncertaintyNotice({ notes }: { notes: string[] }) {
  if (!notes.length) return null;
  return (
    <div className="rounded border border-amber-700/30 bg-amber-500/5 p-3">
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-400">Uncertainty</div>
      <ul className="space-y-1 text-xs leading-relaxed text-amber-200/80">
        {notes.map((n, i) => (
          <li key={i} className="flex gap-1.5">
            <span className="text-amber-500">{"⚠"}</span>
            <span>{n}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
