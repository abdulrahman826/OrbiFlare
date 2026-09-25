import type { ReactNode } from "react";

// One consistent family: 24px grid, 1.6px stroke, no fill, square joins. Monochrome (inherits currentColor).
const PATHS: Record<string, ReactNode> = {
  command: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></>,
  events: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="2.5" /></>,
  replay: <path d="M8 5l11 7-11 7z" />,
  facilities: <><path d="M3 21V9l6 3V9l6 3V4h6v17z" /><path d="M3 21h18" /></>,
  twins: <><circle cx="9" cy="12" r="6" /><circle cx="15" cy="12" r="6" /></>,
  gis: <><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z" /><path d="M9 4v14M15 6v14" /></>,
  analytics: <path d="M4 20V10M10 20V4M16 20v-8M2 20h20" />,
  reports: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 13h7M9 17h7" /></>,
  model: <><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></>,
  agent: <path d="M4 6l6 6-6 6M12 19h8" />,
  limitations: <><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18v.5" /></>,
  archive: <><path d="M3 5h18v4H3zM5 9v11h14V9" /><path d="M10 13h4" /></>,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="square" strokeLinejoin="miter" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
