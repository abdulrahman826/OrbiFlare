import { KPI } from "@/components/KPI";
import { PageHeader, Panel, StateBlock } from "@/components/Panel";
import { api } from "@/lib/api";
import { ML_CORRELATION_NOTE, ML_ROLE_NOTE, MODEL_EVALUATION_LABEL } from "@/lib/assessment";

export const dynamic = "force-dynamic";

export default async function ModelPage() {
  const riskAnalytics = await api.analyticsRisk().catch(() => null);
  if (!riskAnalytics) return <StateBlock kind="error" title="Model metrics unavailable">The backend could not be reached.</StateBlock>;
  const m = riskAnalytics.model_metrics;
  const [classA, classB] = m.confusion_matrix.labels;
  const nf = m.no_facility_model;

  return (
    <div className="space-y-3">
      <PageHeader title="ML evidence" sub="Random Forest thermal-source classifier: two classes only, and one evidence component among several. This page exists to prevent over-trust." />

      <div className="rounded border border-sev-medium/30 bg-sev-medium/5 p-3 text-xs text-sev-medium">
        <b>{ML_ROLE_NOTE}</b> Its development labels come from a documented heuristic (facility proximity, persistence and label noise), not from verified outcomes.
        The scores below measure agreement with that heuristic on a random hold-out. They are not real-world fire-detection accuracy and are not an OrbiFlare accuracy figure.
      </div>

      <Panel variant="section" title="Model evaluation" sub={MODEL_EVALUATION_LABEL}>
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-5">
          <KPI label="Macro-F1" value={m.macro_f1 != null ? m.macro_f1.toFixed(3) : "--"} sub="development set" />
          <KPI label="ROC-AUC" value={m.roc_auc ? m.roc_auc.toFixed(3) : "--"} sub="development set" />
          <KPI label="Development rows" value={`${m.n_train} / ${m.n_val}`} sub="fit / hold-out" />
          <KPI label="Version" value={m.model_version} />
          <KPI label="Feature schema" value={m.feature_schema_version ?? "--"} />
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title="Model card">
          <dl className="space-y-1.5 text-xs">
            {[
              ["Model", `Random Forest (${m.model_version})`],
              ["Class A", "Persistent industrial thermal source"],
              ["Class B", "Candidate natural / agricultural fire"],
              ["Not a class", "“Industrial fire” — that is an evidence-fusion hypothesis downstream, never a trained label"],
              ["Inputs", "NASA FIRMS thermal features (VIIRS 375 m), persistence, facility distance when a specific facility is nearby, seasonality"],
              ["Evaluation", `Random hold-out (${m.split_strategy})`],
              ["Labels", "Heuristic development labels — not confirmed outcomes"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-base-700/50 pb-1.5 last:border-0"><dt className="shrink-0 text-base-400">{k}</dt><dd className="text-right text-base-100">{v}</dd></div>
            ))}
          </dl>
        </Panel>
        <Panel variant="section" title="Three signals — never conflated">
          <ul className="space-y-2 text-xs text-base-300">
            <li><b className="text-base-100">ML class probability</b> — how much this event resembles Class A vs Class B in the development data. Not fire probability.</li>
            <li><b className="text-base-100">Thermal behaviour deviation</b> — how unusual the event is for this facility&apos;s own Thermal Twin. Says nothing about cause.</li>
            <li><b className="text-base-100">Operational priority</b> — an explainable score for analysts, combining deviation, ML, persistence, intensity and context. Not a forecast.</li>
          </ul>
        </Panel>
      </div>

      <Panel variant="section" title="When there is no usable facility" sub="Missing facility information is never turned into a distance">
        <ul className="space-y-1.5 text-xs text-base-200">
          <li><b className="text-base-100">Three states.</b> Usable facility context (an identified facility is nearby), low-quality context (only a generic land-use record), and no facility context.</li>
          <li><b className="text-base-100">Two models, same data.</b> With a usable facility the model receives its real distance. Otherwise a second model runs that simply has no facility-distance input. No placeholder distance is used.</li>
          {nf && <li><b className="text-base-100">Development-set evaluation of the distance-free model:</b> macro-F1 <span className="font-mono">{nf.macro_f1.toFixed(3)}</span> (with distance: <span className="font-mono">{m.macro_f1?.toFixed(3)}</span>). The gap shows how much of the score depends on facility distance.</li>}
          {m.ablations && <li><b className="text-base-100">Ablation:</b> without persistence, macro-F1 is <span className="font-mono">{m.ablations.without_persistence.macro_f1.toFixed(3)}</span>; without facility distance, <span className="font-mono">{m.ablations.without_facility_distance.macro_f1.toFixed(3)}</span>.</li>}
        </ul>
      </Panel>

      <Panel variant="section" title="Data separation — what the model never sees">
        <ul className="grid grid-cols-1 gap-2 text-xs text-base-300 md:grid-cols-2">
          <li><b className="text-base-100">Development / evaluation</b> — generated development data with heuristic labels, random hold-out (above).</li>
          <li><b className="text-base-100">Live / NRT</b> — FIRMS observations flow through the pipeline for scoring only; they are never fed back as labels.</li>
          <li><b className="text-base-100">Demo</b> — sample fixtures, always labelled DEMO.</li>
          <li><b className="text-base-100">Historical reference incidents (30)</b> — imported context, <b>not</b> training data and <b>not</b> a benchmark. Historical incident validation requires matching archived FIRMS observations with independently verified incidents. Enforced by an automated isolation test.</li>
        </ul>
      </Panel>

      <Panel variant="section" title="Development labels and facility correlation" sub="Read this before treating ML evidence as confirmation">
        <ul className="space-y-1.5 text-xs text-base-200">
          <li><b className="text-base-100">How Class A was defined.</b> Development labels come from a rule: <span className="font-mono">nearest-facility distance &le; 5 km AND persistence &ge; 2</span>, with injected label noise. There is no verified fire outcome behind it.</li>
          <li><b className="text-base-100">Features that overlap the label rule.</b> {(m.features_overlapping_label_rule ?? []).map((f) => <span key={f} className="mr-1 font-mono">{f}</span>)} are both label inputs and model features. The classifier largely re-learns that rule.</li>
          <li><b className="text-base-100">Where it overlaps with OrbiFlare priority.</b> The priority score also has its own facility-context and persistence factors. The ML signal partly restates both, so ML + facility + persistence are <b>not</b> three independent confirmations. {ML_CORRELATION_NOTE}</li>
          <li><b className="text-base-100">What OrbiFlare does about it.</b> Facility distance reaches the model only when the associated facility record is specific (High/Medium context quality). ML output is one weighted component of the evidence stack and cannot create an alert state or a confirmed event on its own.</li>
        </ul>
      </Panel>

      <Panel variant="section" title="Per-class metrics" sub={MODEL_EVALUATION_LABEL}>
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

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel variant="section" title="Confusion matrix (random hold-out)">
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
                  <td className="pr-2 text-[10px] text-base-400">development label: {m.confusion_matrix.labels[i].split("_")[0]}</td>
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

        <Panel variant="section" title="Feature importance (global)">
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

      <Panel variant="section" title="Caveats">
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
