# Limitations

This is the source document for the in-app [Limitations page](../frontend/src/app/limitations/page.tsx). It is intentionally detailed rather than hidden behind polish.

1. **VIIRS/MODIS spatial resolution** -- ~375m (VIIRS) / ~1km (MODIS) pixels; a detection localizes to that footprint, not to an exact structure or process.
2. **False positives and missed detections** -- known satellite thermal-anomaly artifacts (sun glint, reflective surfaces, sensor noise) and gaps between overpasses/cloud cover.
3. **Thermal source ambiguity** -- a detection alone doesn't identify what, how, or why something is thermally active; OrbiFlare surfaces evidence and alternatives, not a source identification.
4. **Limited industrial-fire ground truth** -- no verified labelled dataset was available for this build.
5. **Proxy labels** -- the ML classifier is trained on a documented proxy-label heuristic with injected noise, explicitly flagged everywhere its output appears. See [docs/ml.md](ml.md).
6. **OSM/facility dataset incompleteness** -- community-maintained data, known gaps especially outside well-mapped regions; absence of a mapped facility doesn't mean no industrial activity.
7. **Facility proximity does not imply causation** -- always rendered as "~X km away", never as attribution.
8. **Baseline availability varies by facility** -- ESTABLISHED / LIMITED / INSUFFICIENT is computed and shown explicitly; deviation is never fabricated to fill a gap.
9. **ML uncertainty** -- low-confidence predictions are flagged as anomaly-candidate signals, not classifications.
10. **Satellite revisit limitations** -- polar-orbiting sensors revisit a location a few times a day; an event's true continuous evolution is not directly observed, only what each pass captured.
11. **Historical archive limitations** -- a Thermal Twin is only as good as the archive available for that facility; short archives or sensor changes can bias what "normal" looks like.
12. **Event clustering sensitivity** -- spatial/temporal clustering thresholds are configurable and affect how detections group into events; grouping is computational, not proof of one physical fire.
13. **Operator validation is required** -- every score/deviation/classification is decision support. No automated action escalates or resolves an incident, and the system cannot autonomously mark an event Extinguished (enforced in `backend/app/alerts/lifecycle.py`, not just by convention).

## What OrbiFlare never claims

- "FIRMS detected a confirmed fire" -- only "detected thermal activity"
- "This facility caused the hotspot" -- only spatial proximity
- "The model detected an industrial fire" -- only a proxy-labelled class probability
- "This event will become a fire" -- only that observed risk has increased
- Risk score as "fire probability" -- it is operational prioritization only
