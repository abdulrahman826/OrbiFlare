import { acqUtc, FIRMS_CONFIDENCE, satelliteName } from "@/lib/firms";
import { fmtNum } from "@/lib/format";
import type { ThermalObservation } from "@/types/domain";

const TH = "whitespace-nowrap px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-base-400";
const TD = "whitespace-nowrap px-2 py-1.5 font-mono text-[11px] text-base-200";

/** The exact NASA FIRMS records that formed an event, with the source fields as returned. */
export function FirmsObservationsTable({ observations }: { observations: ThermalObservation[] }) {
  const rows = [...observations].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse">
        <thead className="border-b border-base-600">
          <tr>
            <th className={TH}>Acquired (UTC)</th><th className={TH}>Latitude</th><th className={TH}>Longitude</th>
            <th className={TH}>Satellite</th><th className={TH}>Product</th>
            <th className={`${TH} text-right`}>FRP (MW)</th><th className={`${TH} text-right`}>BT I-4 (K)</th><th className={`${TH} text-right`}>BT I-5 (K)</th>
            <th className={TH}>FIRMS confidence</th><th className={`${TH} text-right`}>Scan × Track (km)</th><th className={TH}>Day/Night</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((o) => (
            <tr key={o.observation_id} className="border-b border-base-700">
              <td className={TD}>{acqUtc(o.timestamp)}</td>
              <td className={TD}>{o.latitude.toFixed(5)}</td>
              <td className={TD}>{o.longitude.toFixed(5)}</td>
              <td className={TD}>{o.satellite ? `${satelliteName(o.satellite)} (${o.satellite})` : "—"}</td>
              <td className={TD}>{o.source_product ?? "—"}</td>
              <td className={`${TD} text-right`}>{fmtNum(o.frp, 2)}</td>
              <td className={`${TD} text-right`}>{fmtNum(o.brightness_temperature, 1)}</td>
              <td className={`${TD} text-right`}>{fmtNum(o.brightness_temperature_11, 1)}</td>
              <td className={TD}>{FIRMS_CONFIDENCE[o.confidence ?? ""] ?? o.confidence ?? "—"}</td>
              <td className={`${TD} text-right`}>{o.scan != null && o.track != null ? `${o.scan} × ${o.track}` : "—"}</td>
              <td className={TD}>{o.day_night ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
