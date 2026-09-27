TOTAL EVENTS: 1,449
UNCERTAIN: 1,353
INTERPRETED: 96
ACTIONABLE: 121

DOMINANT ROOT CAUSE:
Every one of the 1,353 uncertain events is a short detection that fails the persistence gate (max 5 observations, max 1.7 h; 78.1 % are a single observation) AND 95.7 % (1,295) have no usable facility context (893 with no facility in the 3 km radius = 66.0 %, 402 with only a generic LOW-quality land-use record = 29.7 %). With neither persistence nor a usable facility, no production rule has a positive signal to build a candidate on.

SECONDARY ROOT CAUSE:
47 events (3.5 % of uncertain) DO meet the industrial evidence threshold (usable heat-relevant facility + recurrence at the facility, industrial score >= 2.0 with 2 distinct signals) but are suppressed by the rule "agricultural-type score must be < 1.0": a single short-lived detection adds 0.5 and an ML Class B result adds 0.5, i.e. exactly 1.0.

STRONG-BUT-UNCERTAIN:
46 events (3.4 % of uncertain) have >= 3 dimensions of existing evidence (45 = usable facility + ML class + established Thermal Twin; 1 = established twin + deviation 50 + >= 4 observations). 47 events meet the industrial rule but are suppressed (see above).

GENUINELY LOW-EVIDENCE:
912 events (67.4 %) on the strict definition (<= 2 observations, no usable facility, no usable baseline, no meaningful deviation, LOW risk, not persistent); 1,327 (98.1 %) on the broad definition (LOW risk, not persistent, no meaningful deviation, < 4 observations).

KEY FINDING:
The 1,353 are overwhelmingly genuinely low-evidence: single, short detections (median 1 observation, 0 h duration, median risk 1.5, none above 24.1, all LOW) with no usable facility. A small, distinct group (47 events, 3.5 %) has facility + recurrence evidence that meets the industrial rule but is blocked by the agricultural counter-evidence gate, which is driven by the same fact (a one-observation event) that the ML Class B result reflects.

PRODUCTION LOGIC CHANGED:
NO

---

AUDIT ONLY. Method: `scripts/audit_uncertain_events.py` (untracked; not part of the application) opens the database read-only (`mode=ro`), builds each stored event, and calls the unchanged production `source_interpretation.interpret()` on it. It reproduces the live API exactly (Uncertain 1,353 / Persistent 52 / Industrial 44). Reasons are reconstructed from the production gates, not invented. Outputs (CSV / JSON of all 1,449 events) are outside the repository.

# 1. Executive Answer

Why are 1,353 events uncertain? Because they are the population of single/short detections with nothing to attribute them with. Percentages (of the 1,353):

* 100 % are not persistent by the production rule (>= 6 observations or >= 6 h): observations 1 = 1,057, 2 = 218, 3 = 52, 4 = 21, 5 = 5; longest duration 1.7 h.
* 95.7 % have no usable facility (66.0 % none, 29.7 % generic LOW-quality land use). Only 58 (4.3 %) have a usable heat-relevant facility.
* 95.7 % have no ML class (the ML only assigns a class when a usable facility exists).
* 100 % are outside the crop-burning months (all 1,449 events were first detected in September) and have no typed FIRMS history at their location.
* 99.9 % have no meaningful deviation from a baseline (only 1 has deviation >= 50 with an established/limited baseline).
* 3.5 % (47) are strong on facility + recurrence but suppressed by the agricultural counter-evidence gate.

# 2. Current Interpretation Decision Tree (backend/app/intelligence/source_interpretation.py, `interpret()`)

```
EVENT (obs, duration, first_detected month, facility association, stored ML class, twin history, typed FIRMS history)
 usable      = facility within 3 km AND quality in {HIGH, MEDIUM, unclassified}      (LOW quality = "not usable")
 persistent  = obs >= 6 OR duration >= 6 h
 transient   = obs <= 2 AND duration < 3 h
 agri_season = first_detected month in {4, 5, 10, 11}

 Signals (weights):
  INDUSTRIAL  facility_context: usable + heat-relevant type -> HIGH quality 2.0 / MEDIUM 1.0
              persistence: persistent AND usable -> 1.0            (persistent and NOT usable supports PERSISTENT only)
              recurrence: usable and >= 2 earlier events at the facility -> 0.75 (>= 4 events -> 1.5)
              firms_type: >= 5 typed historical detections and >= 50 % "static land source" -> 1.5
              ml_evidence: ML Class A -> 0.5
  AGRICULTURAL transient (not persistent) -> 0.5 ; agri_season -> 1.0 ; firms_type <= 10 % static -> 1.5 ; ML Class B -> 0.5
  contra/unavailable lists: LOW-quality facility, non-heat facility, no facility, no land-use dataset, no FIRMS type, no ML class

 ind_ok  = industrial score >= 2.0 AND >= 2 distinct industrial signals
 agr_ok  = agricultural score >= 1.5 AND >= 2 distinct signals AND NOT usable
 natural_ok = usable NON-heat facility AND transient AND NOT agri_season AND industrial < 1.5 AND agricultural < 1.5

 1. ind_ok AND agricultural score < 1.0          -> INDUSTRIAL candidate   (strength HIGH >= 4.0, MODERATE >= 3.0, else LOW; one step lower if any agri score > 0)
 2. agr_ok  AND industrial score < 1.0           -> AGRICULTURAL candidate (MODERATE >= 2.5, else LOW)
 3. industrial >= 1.5 AND agricultural >= 1.5    -> UNCERTAIN (conflict)
 4. persistent                                   -> PERSISTENT thermal-source candidate (MODERATE if obs >= 10 and >= 6 h, else LOW)
 5. natural_ok                                   -> NATURAL/OTHER candidate (LOW)
 6. otherwise                                    -> UNCERTAIN
```
So an event reaches Uncertain only by (a) being non-persistent (rule 4 catches every persistent event that is not industrial/agricultural/conflict), and (b) having no qualifying industrial/agricultural/natural case. ML never decides (0.5 weight, facility-informed). Nothing in the risk engine is involved.

# 3. 1,353 Uncertain Event Breakdown (PRIMARY root cause, one per event, by production gate order)

| Primary root cause | Events | % of uncertain | % of all |
|---|---|---|---|
| No facility context within the radius, and not persistent | 893 | 66.0 % | 61.6 % |
| Only a generic LOW-quality land-use record nearby (not counted), and not persistent | 402 | 29.7 % | 27.7 % |
| Industrial threshold MET (facility + recurrence >= 2.0) but BLOCKED by agricultural counter-evidence >= 1.0 (short detection 0.5 + ML Class B 0.5) | 47 | 3.5 % | 3.2 % |
| Usable heat-relevant facility but industrial score < 2.0 or < 2 distinct signals | 11 | 0.8 % | 0.8 % |
| Conflicting evidence (rule 3) | 0 | 0 % | 0 % |

# 4. Contributing Evidence Breakdown (multi-label; an event appears in several rows)

| Condition | Events | % of uncertain |
|---|---|---|
| Not persistent (< 6 obs and < 6 h) | 1,353 | 100 % |
| Outside crop-burning months | 1,353 | 100 % |
| No usable FIRMS type history at the location | 1,353 | 100 % |
| No meaningful deviation / no baseline to deviate from | 1,352 | 99.9 % |
| No ML class (no usable facility) | 1,295 | 95.7 % |
| Short-lived detection (<= 2 obs, < 3 h) -> adds an agricultural-type signal | 1,275 | 94.2 % |
| Single observation | 1,057 | 78.1 % |
| No facility context / no Thermal Twin | 893 | 66.0 % |
| LOW-quality (generic land-use) facility | 402 | 29.7 % |
| Thermal Twin INSUFFICIENT | 79 | 5.8 % |
| ML Class B (counts only toward agricultural) | 57 | 4.2 % |
| Industrial threshold met but suppressed by agricultural counter-evidence | 47 | 3.5 % |
| Thermal Twin LIMITED | 39 | 2.9 % |
| Recurrence not established (< 2 earlier events) | 10 | 0.7 % |
| ML Class A (half weight, cannot decide alone) | 1 | 0.1 % |

# 5. Thermal Twin Analysis (interpretation x Thermal Twin state)

| | ESTABLISHED | LIMITED | INSUFFICIENT | NONE (no facility) |
|---|---|---|---|---|
| Uncertain (1,353) | 342 | 39 | 79 | 893 |
| Interpreted (96) | 68 | 1 | 1 | 26 |
| - Industrial (44) | 42 | 1 | 1 | 0 |
| - Persistent (52) | 26 | 0 | 0 | 26 |

Missing history does NOT explain most of the uncertainty: 342 uncertain events sit on ESTABLISHED twins (297 of them at generic LOW-quality "industrial" land-use records, which do not count as evidence). The dominant gap is facility identity and persistence, not baseline depth.

# 6. Facility Context Analysis

| Uncertain events with | Count |
|---|---|
| No facility | 893 |
| LOW-quality facility | 402 (399 generic `industrial`) |
| MEDIUM-quality | 19 |
| HIGH-quality | 39 |
| Usable (HIGH + MEDIUM, all heat-relevant) | 58 |

Uncertain events that remain uncertain although facility context exists: **460** (58 usable + 402 generic). Of these 460: 430 have Thermal Twin history, 381 an established/limited twin, 0 are persistent, 1 has meaningful deviation, 58 have an ML class. Of the 58 usable: 57 are single-observation events; 47 are the suppressed group; 11 fall short of 2.0 / 2 signals.

# 7. Behaviour Strength

* Observations: median 1, p95 3, max 5. >= 4 obs: 26; >= 6: 0; >= 10: 0. Duration: median 0 h, p95 0.9 h, max 1.7 h.
* Persistent by the production rule: 0. Recurrence at the facility (>= 2 earlier events): 393.
* Deviation (where a baseline exists, n = 381): median 16.7, p95 25, max 50; deviation >= 50: 1 (established baseline).
* Trajectory: INSUFFICIENT_DATA 1,057, STABLE 284, INCREASING 12, ESCALATING 0.
* Risk: median 1.5, p95 10.3, max 24.1; severity: all 1,353 LOW (0 MEDIUM, 0 HIGH/CRITICAL).
* FIRMS confidence of their observations: nominal 1,536, low 207, high 15. NOAA-21 889 / NOAA-20 869; day 1,019 / night 739. Peak FRP median 2.8 MW (interpreted events: 3.3 MW).

They are genuinely weak on every behavioural dimension the system measures.

# 8. Strong-but-Uncertain Events

Definition (existing fields/thresholds only): uncertain AND >= 3 of {usable facility, persistent, meaningful deviation (E/L baseline, >= 50), ML class assigned, established twin, ESCALATING, MEDIUM+ risk, >= 4 observations}.
**46 events (3.4 %)**; none reach 4 dimensions. Profiles: 45 x {usable heat facility + ML class + established twin}; 1 x {deviation 50 + established twin + >= 4 obs}.
Examples (all LOW risk): EVT-4E0D58430B (Nagarnar Steel Plant, HIGH quality, twin ESTABLISHED, dev 16.7, ML Class B, 1 obs); EVT-031433BB74 (DHOLPUR gas, HIGH, dev 25); EVT-28746B0B9D (Crown Cement Factory, HIGH, dev 25); EVT-C540B72076 / EVT-C574153719 (brickyards, MEDIUM); EVT-CB76D1920C (only generic land-use nearby, 4 obs, dev 50, risk 24.1, trajectory INCREASING).
Common profile: a single observation beside an identified industrial facility with a long history there, which the full ML model reads as Class B because persistence = 1.

# 9. Genuinely Low-Evidence Events

| Property (of 1,353) | Events | % |
|---|---|---|
| <= 2 observations | 1,275 | 94.2 % |
| Single observation | 1,057 | 78.1 % |
| No facility | 893 | 66.0 % |
| No usable facility | 1,295 | 95.7 % |
| No usable baseline (none/insufficient) | 972 | 71.8 % |
| No ML class | 1,295 | 95.7 % |
| No meaningful deviation | 1,352 | 99.9 % |
| LOW risk | 1,353 | 100 % |
| Duration < 1 h | 1,344 | 99.3 % |

Strict (all of: <= 2 obs, no usable facility, no usable baseline, no meaningful deviation, LOW risk, not persistent): **912 (67.4 %)**. Broad (LOW risk, not persistent, no meaningful deviation, < 4 obs): **1,327 (98.1 %)**. The 1,353 is mostly the expected outcome.

# 10. Why Agricultural = 0 (exact)

Rule: agricultural score >= 1.5 with >= 2 distinct signals and NO usable facility. Signals: season 1.0, transient 0.5, FIRMS type (vegetation) 1.5, ML Class B 0.5.
* **Season**: all 1,449 events were first detected in month 9; the crop-burning months are 4, 5, 10, 11. Season signal = 0 for every event.
* Transient: 1,299 events carry the 0.5 transient signal (1,218 of them with no usable facility) - alone insufficient (needs 1.5 and 2 signals).
* ML Class B: 57 events, all with a usable facility (ML only runs with one), so the "no usable facility" condition fails; and 0 of the "Class B + transient + no usable facility" combination exists.
* FIRMS type: 0 events have >= 5 typed historical detections at their location with <= 10 % static. NRT rows carry no type.
* Land-use / vegetation dataset: absent.
Maximum agricultural score in the data = 1.0. Zero is caused by the live data being September (no season signal), no typed history, and no land-use data - not by a bug.

# 11. Why Natural/Other = 0 (exact)

Rule: a usable, identified, NON-heat facility nearby AND transient AND outside crop months AND no industrial/agricultural evidence. Events with a usable non-heat facility: **0** (all 58 usable facilities are heat-relevant types; generic land-use records are LOW quality and never count). The required positive evidence never occurs in the data, and no natural-context dataset (forest, water, land cover) exists. Absence of a facility is deliberately not evidence.

# 12. Actionable Events (121 active = 122 stored; one event is EXTINGUISHED)

* Interpreted and actionable: 95 active (96 stored: 44 industrial, 52 persistent) - every interpreted event is actionable by definition.
* Uncertain and actionable: **26** - 25 because of >= 4 observations, 1 because of >= 4 observations + meaningful deviation (EVT-CB76D1920C: established twin, deviation 50).
* Those 26: all LOW severity, risk 5.0-24.1 (median 7.5), observations 4-5, deviation median 0 (max 50), facility: 16 none / 10 LOW-quality generic, twin: 16 NONE / 10 ESTABLISHED, interpretation = Uncertain.
So the product still surfaces repeated detections when attribution is uncertain, but the operational-priority engine (risk) rates none of them MEDIUM or higher.

# 13. What This Means for OrbiFlare

A. Demonstrably doing well: it does not over-claim (93 % of events are labelled Uncertain rather than forced); it surfaces every persistent event as at least a persistent-source candidate (52 of 52 persistent events; none is uncertain); the 44 industrial candidates all have a usable facility and ML Class A; risk is separate from interpretation and every uncertain event is LOW risk.
B. Cannot establish: source type for single short detections (78 % are one observation); agricultural or natural origin (no season signal in September, no land-use data, no typed history); anything for events without an identified facility.
C. Evidence missing: land cover / land use; typed FIRMS history for NOAA-21 and NRT (only NOAA-20 Standard Processing carries type, through 2026-06-30); repeat observations; imagery; identified (non-generic) facility records - 402 events sit next to a generic `industrial` land-use record.
D. Limitations: facility data is 80 % generic land use; a one-observation event can never be persistent; the ML class for one-observation events leans Class B by construction (persistence is a label input), which feeds the suppression gate.

Data note discovered during the audit (not caused by it): EVT-0C6605D015 was moved DETECTED -> VALIDATING -> ALERTED -> ESCALATED -> MONITORING -> EXTINGUISHED by actor "operator" within 8 seconds on 2026-09-25 10:42 UTC (5 alert_history rows). That is why the UI shows 1,448 active. It pre-dates this audit; I did not change it and cannot tell from the database who triggered it (it matches operator buttons being clicked during earlier browser sessions).

# 14. Potential Future Improvements (DOCUMENT ONLY - nothing implemented)

| # | Improvement | Evidence gap it addresses | Expected usefulness | Scientific risk |
|---|---|---|---|---|
| 1 | Review the `agricultural score < 1.0` industrial gate so that a one-observation event's ML Class B result (itself driven by persistence = 1) is not counted twice against an otherwise-met industrial rule (47 events) | Double use of "short-lived" evidence | Medium: moves <= 47 events (3.5 %) | Medium: would increase industrial candidates from single detections; needs a persistence/second-signal safeguard |
| 2 | Add a land-use / land-cover layer (e.g. ESA WorldCover / Copernicus) as an explicit signal | No agricultural or natural evidence in any month | High for agricultural and natural classes | Low (new independent evidence) |
| 3 | Better facility records: promote generic `industrial` polygons to named installations where the data allows | 402 events beside LOW-quality land use | Medium-high | Low-medium (must not overstate) |
| 4 | Extend FIRMS `type` coverage (NOAA-21 SP when NASA publishes it) | 0 events have usable typed history | Medium | Low |
| 5 | Re-observation policy (second overpass window) before interpreting single detections | 78 % are one observation | High for reducing uncertainty honestly | Low |
| 6 | Show "why uncertain" (primary gate) in the investigation panel | Users cannot see which gate failed | Medium (transparency) | Very low |
| 7 | Evaluate the interpretation on independently verified incidents | No ground truth for the candidate labels | High (validation) | Low; needs archive data |

# Safety check (after the audit)

* `git diff` hash before = after (production files unchanged); the only new file is the untracked `scripts/audit_uncertain_events.py`, plus this report.
* Database: all 13 table row counts identical (events 1,449; alerts 1,449; alert_history 5; observations 2,499; risk_assessments 1,449); content hashes of events (id/status/severity/risk/classification/facility/trajectory), alerts, alert history, risk assessments and observations identical before/after.
* Live API after the audit: 1,449 events, Uncertain 1,353 / Persistent 52 / Industrial 44; statuses DETECTED 1,448 / EXTINGUISHED 1. No refresh, migration or restart was performed.

UNCERTAIN ROOT-CAUSE AUDIT COMPLETE — NO PRODUCTION LOGIC CHANGED.
