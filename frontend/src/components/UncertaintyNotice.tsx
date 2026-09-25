export function UncertaintyNotice({ notes }: { notes: string[] }) {
  if (!notes.length) return null;
  return (
    <ul className="space-y-1.5 text-xs leading-relaxed text-base-300">
      {notes.map((n, i) => (
        <li key={i} className="flex gap-2">
          <span className="text-sev-medium">△</span>
          <span>{n}</span>
        </li>
      ))}
    </ul>
  );
}
