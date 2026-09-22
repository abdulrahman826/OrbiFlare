import { Panel } from "@/components/Panel";

const LIMITATIONS = [
  {
    title: "VIIRS/MODIS spatial resolution",
    body: "VIIRS thermal-anomaly pixels are ~375m; MODIS pixels are ~1km. A single detection can only be localized to that footprint, not to an exact structure or process within a facility.",
  },
  {
    title: "False positives and missed detections",
    body: "Satellite thermal-anomaly products have known false-positive sources (sun glint, reflective surfaces, sensor artifacts) and can miss real thermal activity between overpasses or under cloud cover.",
  },
  {
    title: "Thermal source ambiguity",
    body: "A detected thermal anomaly does not by itself indicate what is burning, how, or why. OrbiFlare surfaces evidence and alternative explanations -- it does not claim to identify the physical source.",
  },
  {
    title: "Limited industrial-fire ground truth",
    body: "No verified, labelled dataset of confirmed industrial fires vs. routine thermal activity was available for this build. The classifier is trained on a documented proxy-label heuristic, not real outcomes.",
  },
  {
    title: "Proxy labels",
    body: "Where machine learning is used, training labels are proxy labels (facility proximity + persistence + intensity + seasonality) with injected noise -- explicitly flagged wherever model output is shown.",
  },
  {
    title: "OSM/facility dataset incompleteness",
    body: "OpenStreetMap-derived facility data is community-maintained and known to be incomplete, especially outside well-mapped regions. Absence of a mapped facility does not mean no industrial activity exists nearby.",
  },
  {
    title: "Facility proximity does not imply causation",
    body: "Every place OrbiFlare shows a nearby facility, it is described as spatial context only (\"located approximately X km away\"), never as the confirmed source of a thermal event.",
  },
  {
    title: "Baseline availability varies by facility",
    body: "Thermal Twins require enough historical events/observations to be statistically meaningful. Facilities without enough history are explicitly marked INSUFFICIENT baseline -- deviation is never fabricated to fill the gap.",
  },
  {
    title: "ML uncertainty",
    body: "The Random Forest classifier's confidence can be low, especially near its decision boundary. Low-confidence predictions are flagged as anomaly candidates, not treated as a classification.",
  },
  {
    title: "Satellite revisit limitations",
    body: "Polar-orbiting sensors like VIIRS/MODIS revisit a given location only a few times per day, so an event's real evolution between overpasses is not directly observed -- only what was captured at each pass.",
  },
  {
    title: "Historical archive limitations",
    body: "Thermal Twins are only as good as the historical archive available for a facility. Short archives, gaps, or sensor changes over time can bias what 'normal' looks like.",
  },
  {
    title: "Event clustering sensitivity",
    body: "Grouping raw detections into events depends on configured spatial/temporal thresholds. Different thresholds can split or merge events differently -- clustering is a computational grouping, not proof of a single physical fire.",
  },
  {
    title: "Operator validation is required",
    body: "Every risk score, deviation, and classification in OrbiFlare is decision support for a human analyst. No automated action escalates or resolves an incident -- and the system can never autonomously mark an event Extinguished.",
  },
];

export default function LimitationsPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Limitations</h1>
        <p className="max-w-3xl text-sm text-base-400">
          OrbiFlare is designed to be scientifically honest about what it can and cannot claim. This page documents every
          material limitation of the current build, rather than hiding them behind a polished interface.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {LIMITATIONS.map((l, i) => (
          <Panel key={l.title}>
            <div className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs text-base-500">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3 className="text-sm font-medium text-base-100">{l.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-base-400">{l.body}</p>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="What OrbiFlare never claims">
        <ul className="grid grid-cols-1 gap-2 text-xs text-base-300 sm:grid-cols-2">
          <li>{"✗"} &ldquo;FIRMS detected a confirmed fire&rdquo; -- only &ldquo;detected thermal activity&rdquo;</li>
          <li>{"✗"} &ldquo;This facility caused the hotspot&rdquo; -- only spatial proximity</li>
          <li>{"✗"} &ldquo;The model detected an industrial fire&rdquo; -- only a proxy-labelled class probability</li>
          <li>{"✗"} &ldquo;This event will become a fire&rdquo; -- only that observed risk has increased</li>
          <li>{"✗"} Risk score as &ldquo;fire probability&rdquo; -- it is operational prioritization only</li>
        </ul>
      </Panel>
    </div>
  );
}
