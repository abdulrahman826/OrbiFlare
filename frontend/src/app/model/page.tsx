import { KPI } from "@/components/KPI";
import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ModelPage() {
  const riskAnalytics = await api.analyticsRisk();
  const m = riskAnalytics.model_metrics;
  const [classA, classB] = m.confusion_matrix.labels;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Model</h1>
        <p className="text-sm text-base-400">Random Forest thermal-source classifier -- two classes only, one evidence signal among several.</p>
      </div>

      <div className="rounded border border-sev-medium/30 bg-sev-medium/5 p-3 text-xs text-sev-medium">
        <b>Proxy-label model.</b> There is no verified real-world industrial-fire ground truth available. Training labels come from a
        documented facility-proximity + persistence + intensity + seasonality heuristic with injected label noise -- not confirmed outcomes.
        The metrics below describe how well the model recovers that heuristic on a geographic holdout, not real-world detection accuracy.
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <KPI label="Accuracy (holdout)" value={`${(m.accuracy * 100).toFixed(1)}%`} />
        <KPI label="ROC-AUC" value={m.roc_auc ? m.roc_auc.toFixed(3) : "--"} />
        <KPI label="Train size" value={m.n_train} />
        <KPI label="Validation size" value={m.n_val} />
        <KPI label="Version" value={m.model_version} />
      </div>

      <Panel title="Per-class metrics">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase text-base-400">
              <th className="pb-2">Class</th>
              <th className="pb-2 text-right">Precision</th>
              <th className="pb-2 text-right">Recall</th>
              <th className="pb-2 text-right">F1</th>
            </tr>
          </thead>
          <tbody>
            {[classA, classB].map((c) => (
              <tr key={c} className="border-t border-base-700/60">
                <td className="py-2 text-base-200">{c}</td>
                <td className="py-2 text-right font-mono text-base-100">{m.precision[c]?.toFixed(2)}</td>
                <td className="py-2 text-right font-mono text-base-100">{m.recall[c]?.toFixed(2)}</td>
                <td className="py-2 text-right font-mono text-base-100">{m.f1[c]?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Confusion Matrix (holdout)">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th></th>
                {m.confusion_matrix.labels.map((l) => (
                  <th key={l} className="pb-1 text-[10px] font-normal text-base-400">
                    pred: {l.split("_")[0]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {m.confusion_matrix.matrix.map((row, i) => (
                <tr key={i}>
                  <td className="pr-2 text-[10px] text-base-400">actual: {m.confusion_matrix.labels[i].split("_")[0]}</td>
                  {row.map((v, j) => (
                    <td key={j} className="border border-base-700 p-2 text-center font-mono text-base-100">
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Feature Importance">
          {Object.entries(m.feature_importance)
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => (
              <div key={k} className="mb-2 flex items-center gap-2">
                <span className="w-40 shrink-0 text-xs text-base-300">{k}</span>
                <div className="h-2 flex-1 rounded bg-base-700">
                  <div className="h-full rounded bg-accent" style={{ width: `${v * 100}%` }} />
                </div>
                <span className="w-10 shrink-0 text-right font-mono text-[11px] text-base-400">{(v * 100).toFixed(0)}%</span>
              </div>
            ))}
        </Panel>
      </div>

      <Panel title="Caveats">
        <ul className="space-y-1.5">
          {m.caveats.map((c, i) => (
            <li key={i} className="flex gap-1.5 text-xs text-base-300">
              <span className="text-sev-medium">{"⚠"}</span>
              {c}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
