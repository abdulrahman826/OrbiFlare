# OrbiFlare Accuracy & Validation Report

_Generated 2026-09-25 05:13 UTC by `scripts/validate_accuracy.py`. Evaluation only: production model, thresholds and events were not modified._

## Executive Summary

**There is no defensible overall real-world accuracy figure for OrbiFlare, and none is reported.** No verified ground truth exists: the RF is trained and scored on synthetic, proxy-labelled data, and none of the 30 historical incidents can be evaluated because no FIRMS data for their dates is available. What *has* been validated is engineering fidelity:

- FIRMS ingestion fidelity: 1346 / 1346 = 100.0%  _(population: rows NASA returns right now for the configured products/window; method: csv-module parse vs stored row)_
- Facility association recomputation: 1012 / 1012 = 100.0%  _(population: all live events; method: brute-force haversine to every indexed facility (numpy), nearest within radius; id equal and distance within 0.02 km; 'none' must also match)_
- RF vs proxy labels (synthetic, held-out 20%): accuracy 0.811, macro-F1 0.810, balanced accuracy 0.812. This measures recovery of the labelling heuristic, not fire detection.
- Removing the facility-distance feature changes macro-F1 by -0.073 (mean over 20 corpora: -0.095).
- Historical backtest: 0 / 30 = 0.0%  _(population: 30 curated historical incidents (2019-2023); method: incident date inside the stored FIRMS observation window)_ evaluable.
- Backend tests: 275 passed, 0 failed, 0 skipped (of 275).

## A. FIRMS Ingestion Fidelity

Not an accuracy claim. 1346 / 1346 = 100.0%  _(population: rows NASA returns right now for the configured products/window; method: csv-module parse vs stored row)_

- Observations checked: 1346; not yet in the database (published after last refresh): 0; field mismatches: none
- `VIIRS_NOAA21_NRT`: {'rows_from_nasa_now': 634, 'exact': 634, 'field_mismatch': 0, 'not_in_database': 0}
- `VIIRS_NOAA20_NRT`: {'rows_from_nasa_now': 712, 'exact': 712, 'field_mismatch': 0, 'not_in_database': 0}

## B. Facility Association Validation

Spatial association only, not causation. 1012 / 1012 = 100.0%  _(population: all live events; method: brute-force haversine to every indexed facility (numpy), nearest within radius; id equal and distance within 0.02 km; 'none' must also match)_

- Indexed facilities: 38,189; radius 3.0 km; events with context: 431; mismatches: {'wrong_facility': 0, 'wrong_distance': 0, 'context_missing': 0, 'context_spurious': 0}; context quality (events): {'MEDIUM': 22, 'LOW': 347, 'HIGH': 62}

## C. RF Proxy-Label Evaluation

**PROXY-LABEL DEVELOPMENT EVALUATION. Not real-world fire accuracy, not industrial-fire detection accuracy, not fire prediction accuracy.**

- Class A = persistent industrial thermal source; Class B = natural/agricultural fire *candidate*.
- Population: 285 held-out rows of a 1,400-row **synthetic** corpus (no real FIRMS observation is used). Proxy label = `CLASS_A if dist_to_facility <= 5 km and persistence >= 2`, then 16% random label flips.
- **The proxy label is built from facility proximity, and facility distance is also a model feature (and persistence is both label input and feature).** The evaluation is therefore partly circular.
- Holdout: The 'geographic holdout' is a random 20% row split: region_id carries no geography, so it does NOT test spatial generalisation.
- Reproduction check: stored metrics (trained 2026-09-25T04:50:10.453255) vs re-run: identical = True

| | Class A precision | recall | F1 | support | Class B precision | recall | F1 | support |
|---|---|---|---|---|---|---|---|---|
| RF | 0.779 | 0.837 | 0.807 | 135 | 0.843 | 0.787 | 0.814 | 150 |

Confusion matrix (rows = proxy label A,B; columns = predicted A,B): `[[113, 22], [32, 118]]`

- accuracy 0.811 (bootstrap 95% CI 0.765-0.853, n=285), balanced accuracy 0.812, macro-F1 0.810, weighted-F1 0.811
- ROC-AUC 0.858; PR-AUC class A 0.810 (prevalence 0.474); PR-AUC class B 0.863
- Reference: the proxy rule itself applied to the observed features scores accuracy 0.825 (macro-F1 0.824) with no learning; label-noise ceiling is ~0.84. The RF is essentially re-learning the rule.

## D. Facility-Distance Ablation

Same corpus, split and hyper-parameters; evaluation only.

| Features | accuracy | macro-F1 | balanced acc | PR-AUC A | dMacro-F1 vs production |
|---|---|---|---|---|---|
| all_features (production) | 0.811 | 0.810 | 0.812 | 0.810 | +0.000 |
| without dist_nearest_facility_km | 0.740 | 0.737 | 0.737 | 0.739 | -0.073 |
| without persistence_count | 0.789 | 0.789 | 0.792 | 0.770 | -0.021 |
| without dist AND persistence (the two label-rule inputs) | 0.698 | 0.697 | 0.696 | 0.710 | -0.114 |
| only dist AND persistence | 0.800 | 0.800 | 0.802 | 0.777 | -0.010 |

- Across 20 independently generated corpora (100..119): macro-F1 with distance 0.814 +/- 0.020; without 0.719 +/- 0.032; mean drop 0.095.
- Impurity importance: {"bt_kelvin": 0.134, "frp_mw": 0.118, "persistence_count": 0.257, "dist_nearest_facility_km": 0.412, "agri_season_flag": 0.028, "day_night_bin": 0.016, "acq_month": 0.035}
- Permutation importance (macro-F1 drop on holdout): {"bt_kelvin": -0.001, "frp_mw": 0.002, "persistence_count": 0.092, "dist_nearest_facility_km": 0.213, "agri_season_flag": -0.004, "day_night_bin": -0.0, "acq_month": -0.001}
- Interpretation: see `interpretation` below.

**Interpretation:** Removing facility distance alone changes macro-F1 by -0.073; removing both label-rule inputs (distance and persistence) changes it by -0.114 (macro-F1 0.697). Performance is carried by the same signals used to construct the proxy labels; the remaining features (BT, FRP, month, day/night) are generated from the same latent 'industrial world' flag, so they are correlated with the label for synthetic reasons, not because the physics was learned.

## E. 50 km Sentinel Analysis

- Training distance percentiles (all): {"p0": 0.04, "p1": 0.08, "p5": 0.25, "p25": 1.56, "p50": 4.0, "p75": 13.41, "p95": 43.6, "p99": 79.01, "p100": 172.0}
- Class A: {"p0": 0.05, "p1": 0.06, "p5": 0.19, "p25": 0.9, "p50": 1.96, "p75": 3.79, "p95": 24.95, "p99": 62.33, "p100": 103.05}
- Class B: {"p0": 0.04, "p1": 0.16, "p5": 0.68, "p25": 3.96, "p50": 9.84, "p75": 21.76, "p95": 52.48, "p99": 83.28, "p100": 172.0}
- 89 / 1400 = 6.36%  _(population: 1,400 synthetic training corpus rows; method: count)_
- 22 / 1400 = 1.57%  _(population: training corpus; method: count)_
- 13 / 673 = 1.93%  _(population: class A rows; method: count)_
- 51 / 727 = 7.02%  _(population: class B rows; method: count)_
- 17 / 727 = 2.34%  _(population: class B rows; method: count)_
- class_A_maximum_distance_km: 103.04721939657229
- P(class A) as distance varies (other features fixed): `{"typical live event (median bt, frp)": {"0.1": 0.4563, "1": 0.4393, "2": 0.3983, "3": 0.3738, "5": 0.3348, "10": 0.2575, "20": 0.2979, "30": 0.3041, "40": 0.3247, "50": 0.3381, "80": 0.3597, "120": 0.3597}, "persistent live event (persistence 6)": {"0.1": 0.8458, "1": 0.8631, "2": 0.8305, "3": 0.8229, "5": 0.5794, "10": 0.247, "20": 0.2709, "30": 0.2875, "40": 0.3206, "50": 0.3289, "80": 0.3433, "120": 0.3433}}`
- Live LOW-quality events (347): 125 / 347 = 36.02%  _(population: live events with LOW-quality facility context; method: predict_proba >= 0.5, everything else identical)_; mean P(A) with actual generic-record distance 0.446 vs sentinel 0.236 (shift -0.210)

**Assessment:** 50 km is INSIDE the training range (max 172.0 km) but sparsely populated: 64/1400 rows lie at >= 45 km (51/727 class-B rows, 13/673 class-A rows; the class-A ones are label-noise flips). The forest's response to distance is NOT monotone (see the sweep: P(A) is lower at 10 km than at 50 km for typical events) because it has few samples in the far tail, so 50 km is read as 'somewhat far', not as a clean 'no facility'. That is the intended meaning for a LOW-quality generic record, but it is also an ARTIFICIAL classification effect: the true distance is unknown-but-within-search-radius, and the model receives a specific far value. Recommendation (NOT applied): represent 'no usable facility' as a missing-value indicator (separate binary feature) or train with an explicit no-facility class, instead of a magic distance.

## F. Historical Incident Backtest

- 0 / 30 = 0.0%  _(population: 30 curated historical incidents (2019-2023); method: incident date inside the stored FIRMS observation window)_
- 30 / 30 = 100.0%  _(population: same; method: same; NOT counted as model failures)_
- 0 / 30 = 0.0%  _(population: same; method: SQL count)_
- Incident dates ['2019-05-24', '2023-11-01']; stored FIRMS window ['2026-09-20 06:20:00.000000', '2026-09-24 21:50:00.000000']; raw parquet: {'path': 'data/raw/firms_observations.parquet', 'rows': 91, 'columns': ['observation_id', 'timestamp', 'latitude', 'longitude', 'sensor', 'brightness_temperature', 'brightness_temperature_11', 'frp', 'confidence', 'day_night', 'source', 'source_id'], 'time_range': ['2026-09-22T06:18:00', '2026-09-22T09:41:00']}
- Acquisition mechanism: The project ingests NEAR-REAL-TIME data only (day_range <= 5 from today). It has no historical/archive acquisition mechanism.
- Surfaced as events / capture rate / top-10% / top-25% / median rank: **not computable** (No incident has FIRMS coverage, so there is nothing to process, surface or rank. No historical observation was invented and no incident was manually labelled.)
- Even with archive data, several of the 30 records are not thermal-anomaly targets at VIIRS scale or are not fires (gas leak, memorial anniversary, stubble-burning reference points, chronic thermal sources), and coordinates are approximate (site/city level).
- Needed: A FIRMS archive extract (Standard Processing, e.g. VIIRS SNPP/NOAA-20 for 2019-2023) for each incident date +/- a few days over India, ingested with the existing local-CSV path and run through the existing event logic. Not done here.

## G. Event Formation Validation

Event/pipeline/lifecycle test files: 101 passed, 0 failed of 101. Full backend suite: {'total': 275, 'passed': 275, 'failed': 0, 'skipped': 0, 'exit_code': 0}

| Behaviour | tests | passed | failed |
|---|---|---|---|
| growth keeps the same event ID | 4 | 4 | 0 |
| unrelated activity gets a separate ID | 5 | 5 | 0 |
| refresh does not duplicate (idempotent) | 1 | 1 | 0 |
| merge is audited | 1 | 1 | 0 |
| split is audited | 2 | 2 | 0 |
| operator state preserved | 6 | 6 | 0 |
| trajectory consistent/preserved | 4 | 4 | 0 |

(Categories are matched by test name; a test can appear in more than one row.)

Live: refresh idempotent = True; merged/split in the real refresh: 0/0 (merge/split are exercised only by tests).

## H. Risk/Replay Validation

- severity_matches_thresholds: 1012 / 1012 = 100.0%  _(population: live events; method: recomputed from config thresholds)_
- stored_risk_equals_event_risk: 1012 / 1012 = 100.0%  _(population: live events; method: SQL join)_
- risk_in_0_100: 1012 / 1012 = 100.0%  _(population: live events; method: range check)_
- trajectory_final_point_equals_event_risk: 1012 / 1012 = 100.0%  _(population: live events with trajectory points; method: SQL)_
- trajectory_timestamps_monotone: 1012 / 1012 = 100.0%  _(population: live events with trajectory points; method: SQL)_
- Limited-baseline cap: {'events': 98, 'cap_pts': 14.0, 'max_observed': 9.34, 'violations': 0}; insufficient/no-baseline events with non-zero deviation: 0; LOW-quality facility with facility risk: 0
- Thresholds {'medium': 35.0, 'high': 60.0, 'critical': 80.0, 'changed_in_this_pass': False}

## I. Live System Statistics

Operational statistics, **not accuracy**.

- firms_observations: 1873
- by_satellite: {'N20': 956, 'N21': 917}
- acquisition_range_utc: ['2026-09-20 06:20:00.000000', '2026-09-24 21:50:00.000000']
- nasa_confidence: {'h': 10, 'l': 121, 'n': 1742}
- synthetic_observations: 0
- synthetic_events: 0
- events: 1012
- severity: {'LOW': 1007, 'MEDIUM': 5}
- trajectory: {'INSUFFICIENT_DATA': 709, 'STABLE': 230, 'ESCALATING': 14, 'INCREASING': 57, 'DECREASING': 2}
- escalating: 14
- persistent_ge6_obs: 41
- status: {'DETECTED': 1012}
- max_risk: 44.0
- facility_context_events: 431
- context_quality: {'MEDIUM': 22, 'LOW': 347, 'HIGH': 62}
- events_no_facility_context: 581
- referenced_facilities: 282
- facility_twins: {'ESTABLISHED': 4, 'INSUFFICIENT': 252, 'LIMITED': 26}
- event_baselines_from_risk: {'INSUFFICIENT': 893, 'LIMITED': 98, 'ESTABLISHED': 21}
- refresh: {'first': {'status': 'OK', 'observations_received': 1346, 'new_observations': 0, 'updated_observations': 0, 'events_total': 1012, 'events_created': 0, 'events_updated': 0, 'events_unchanged': 1012, 'events_merged': 0, 'events_split': 0, 'seconds': 12.1}, 'immediately_after': {'status': 'OK', 'observations_received': 1346, 'new_observations': 0, 'updated_observations': 0, 'events_total': 1012, 'events_created': 0, 'events_updated': 0, 'events_unchanged': 1012, 'events_merged': 0, 'events_split': 0, 'seconds': 11.6}, 'idempotent': True}

**Distribution shift (live features vs RF training range):**
- note: Share of LIVE events whose feature lies outside the range the RF saw in training (synthetic corpus).
- persistence_gt_training_max: 8 / 1012 = 0.79%  _(population: live events; method: training max persistence = 14)_
- frp_gt_training_max: 0 / 1012 = 0.0%  _(population: live events; method: training max FRP = 120)_
- bt_outside_training: 0 / 1012 = 0.0%  _(population: live events; method: training BT range 290..389 K)_
- live_feature_summary: {'bt': {'min': 295.29, 'median': 329.435, 'max': 367.0}, 'frp': {'min': 0.16, 'median': 2.355, 'max': 34.08}, 'obs': {'min': 1.0, 'median': 1.0, 'max': 74.0}}
- live_predicted_class_counts: {None: 928, 'NATURAL_AGRICULTURAL_FIRE_CANDIDATE': 45, 'PERSISTENT_INDUSTRIAL_THERMAL_SOURCE': 39}

## J. Scientific Claim Audit

Scanned 155 files; 62 pattern hits; 61 are negations/denials (safe); **1 need review**.

| file | line | pattern | current wording | recommended |
|---|---|---|---|---|
| README.md | 3 | AI detection claim | **SIH26162** -- AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources Using NASA FIRMS, OSM & Satellite Data. | Official SIH26162 problem-statement title; acceptable only when quoted as the title. Describe the implemented system precisely (analyst console prioritising FIRMS thermal observations) in the surrounding text. |

## K. Visual Validation

See reports/orbiflare_final_hardening_report.md (browser screenshots of Model, Investigation x2, Command Center, Events were captured in this pass; earlier pass covered the remaining pages).

## L. Limitations

- No verified ground truth: the RF has never been evaluated on a real, independently labelled industrial-incident set.
- The RF is trained on a synthetic corpus, not on real FIRMS observations; its 'geographic holdout' is a random row split.
- Proxy labels are built from facility proximity and persistence, which are also model features (circularity); metrics measure recovery of that rule.
- The 50 km sentinel is an unlearned-artefact risk for LOW-quality/no-context events (see E).
- Live events lie partly outside the training range (persistence, FRP); see the distribution-shift block in I.
- Historical incident backtest: 0/30 evaluable; the project has no archive acquisition path.
- Facility association is validated against the same dataset, so it validates the computation, not the completeness/accuracy of OSM/GPPD (most records are generic land-use, LOW quality).
- Baselines are limited by ~5 days of stored NRT history; most facilities are limited or insufficient.
- MAP_KEY rotation is still required externally.

## M. Reproducibility

```
cd <repo>
python scripts/validate_accuracy.py            # full run (needs backend on :8000 and MAP_KEY for network sections)
python scripts/validate_accuracy.py --skip-network --skip-refresh   # offline
```
Seeds: corpus seed 7 (as implemented), RF random_state 42, ablation stability corpora seeds 100-119, bootstrap seed 0. Data: `backend/data/orbiflare.db` (read-only), `data/facilities/osm_gppd_facilities.parquet`, `data/reference/incidents/confirmed_incidents_india.csv`.