import Link from "next/link";
import { BaselineStatus } from "@/components/BaselineStatus";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ThermalTwinsPage() {
  const [twins, facilities] = await Promise.all([api.listThermalTwins(), api.listFacilities()]);
  const facilityById = Object.fromEntries(facilities.map((f) => [f.facility_id, f]));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Facility Thermal Twins</h1>
        <p className="text-sm text-base-400">Multidimensional behavioural baselines learned from each facility&apos;s history.</p>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {twins.map((t) => {
          const f = facilityById[t.facility_id];
          return (
            <Link key={t.facility_id} href={`/thermal-twins/${t.facility_id}`} className="block rounded-md border border-base-700 bg-base-850 p-3 hover:border-accent/50 hover:bg-base-800">
              <div className="flex items-start justify-between">
                <div className="text-sm font-medium text-base-100">{f?.name || t.facility_id}</div>
                <BaselineStatus confidence={t.baseline_confidence} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-base-300">
                <span>Normal FRP: <b className="font-mono text-base-100">{fmtNum(t.normal_frp.median, 0)} MW</b></span>
                <span>Events: <b className="font-mono text-base-100">{t.historical_event_count}</b></span>
              </div>
            </Link>
          );
        })}
      </div>
      {twins.length === 0 && <Panel><p className="text-sm text-base-400">No thermal twins computed yet.</p></Panel>}
    </div>
  );
}
