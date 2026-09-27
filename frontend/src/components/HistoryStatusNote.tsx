import type { HistoryStatus } from "@/types/domain";

/** One line on the historical baseline: coverage when available, an explicit UNAVAILABLE otherwise. Never blocks the live view. */
export function HistoryStatusNote({ status }: { status: HistoryStatus | null }) {
  if (!status || status.state === "UNAVAILABLE") {
    return (
      <p className="text-[11px] text-base-400" data-testid="history-status">
        Historical baseline: <b className="text-base-200">UNAVAILABLE</b>. Thermal Twins use only the live history window; nothing is estimated.
      </p>
    );
  }
  return (
    <p className="text-[11px] text-base-400" data-testid="history-status">
      Historical baseline: <b className="text-base-200">{status.state === "PARTIAL" ? "PARTIAL" : "AVAILABLE"}</b> · history coverage {status.covered_days ?? "—"} / {status.requested_days ?? "—"} days
      {status.window_first && status.window_last ? ` (${status.window_first} → ${status.window_last})` : ""} · {status.facilities_with_history ?? 0} facilities with history.
      Historical observations are kept separate from live detections and never appear as current events.
    </p>
  );
}
