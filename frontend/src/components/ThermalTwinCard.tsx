import { BaselineStatus } from "@/components/BaselineStatus";
import { fmtNum } from "@/lib/format";
import type { ThermalTwin } from "@/types/domain";

export function ThermalTwinCard({ twin }: { twin: ThermalTwin }) {
  return (
    <div className="rounded-md border border-base-700 bg-base-850 p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-base-300">{twin.facility_id}</span>
        <BaselineStatus confidence={twin.baseline_confidence} />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="font-mono text-sm text-base-100">{fmtNum(twin.normal_frp.median, 0)}</div>
          <div className="text-[10px] uppercase text-base-400">Normal FRP (MW)</div>
        </div>
        <div>
          <div className="font-mono text-sm text-base-100">{fmtNum(twin.normal_duration.median)}</div>
          <div className="text-[10px] uppercase text-base-400">Normal Dur. (h)</div>
        </div>
        <div>
          <div className="font-mono text-sm text-base-100">{twin.historical_event_count}</div>
          <div className="text-[10px] uppercase text-base-400">Historical events</div>
        </div>
      </div>
    </div>
  );
}
