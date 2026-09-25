# OrbiFlare — Final Hardening Report

Scope: the six issues found by `reports/orbiflare_accuracy_validation.md`. The architecture (FIRMS → events → facility context → Thermal Twin → deviation → ML evidence → evidence fusion → trajectory → investigation), the risk thresholds (35 / 60 / 80) and the risk weights are unchanged. No synthetic data was added to the live database. `scripts/validate_accuracy.py` was **not modified**; it was re-run as-is (see "Validation re-run").

Every number below was measured in this pass (live data: 1,873 FIRMS observations, 1,012 events; NASA refresh of 2026-09-25).

## 1. Changes made

| # | Issue | Change |
|---|---|---|
| 1 | Event risk ≠ trajectory risk (79 / 1,012 events) | One canonical definition: intensity always uses the **latest observation's FRP** (`risk.latest_observation_frp`, ties broken by observation id). The stored event risk (`pipeline.calculate_risk_stage`) and every trajectory point use it. |
| 2 | 50 km "no facility" sentinel | Removed. Explicit facility state `USABLE / LOW_QUALITY / NONE`; no distance is ever invented. Two models (see §6). |
| 3 | Facility context not clearly qualified | High / Medium / Low each carry an explicit meaning; "Facility context is spatial association, not source attribution. Nearby does not mean caused by." shown in every context section. |
| 4 | Limited baselines looked like established ones | LIMITED deviation badges read "Significant deviation — LIMITED HISTORY" (dashed, muted); evidence from limited history is one strength step weaker and says so; INSUFFICIENT shows no values or badges. |
| 5 | Accuracy claims | Bare "Accuracy (holdout) 81%" removed everywhere. Model page shows "Model evaluation — Development-set evaluation (random hold-out)" with Macro-F1 / ROC-AUC and an explicit "not real-world fire-detection accuracy / not an OrbiFlare accuracy figure". Historical validation is worded neutrally. |
| 6 | Unsafe / internal wording | See §7 and §8. |

## 2. Risk / trajectory consistency

| | Before | After |
|---|---|---|
| Events whose last trajectory point equals the stored event risk (±0.06) | 933 / 1,012 (92.2 %) | **1,012 / 1,012 (100 %)** (validation script, and an independent SQL check) |
| Cause | stored risk used the event's **peak** FRP; trajectory used the **latest** FRP | both use the latest observation's FRP |

Documented relationship: *the event risk is exactly the last point of its risk trajectory; trajectory point k is the canonical risk of the event as it stood after observation k.* The explanation string "Most recent FRP reading of X MW" was already the risk engine's stated intent; the stored value simply did not honour it.

Regression tests (`tests/intelligence/test_risk_trajectory_consistency.py`, 8 tests): peak FRP > latest FRP; latest FRP = peak (rising); peak in the middle; the original failure case (asserts the peak-based and latest-based definitions really differ, and that the stored value equals the latest-based one); ties in timestamp / storage order independence; missing latest FRP fallback; every trajectory point consistent.

## 3. Facility-context changes

* Facility data untouched (no facilities deleted, no names invented). Live: 431 / 1,012 events have context — 62 High, 22 Medium, 347 Low; 581 none. Independent recomputation: **1,012 / 1,012** match (spatial association only).
* Quality meaning (shown under the quality row): High — "High-quality facility context based on available facility metadata."; Medium — "Moderate facility context; source attribution remains uncertain."; Low — "Low-quality spatial context; not treated as strong attribution evidence."
* Backend policy unchanged and re-verified: LOW-quality context contributes 0 to risk (0 violations in 1,012 events) and is not given to the ML as a facility.

## 4. Baseline changes

* Baseline states are unchanged: ESTABLISHED (≥ 4 historical events and ≥ 8 observations), LIMITED (≥ 2 events and ≥ 3 observations), INSUFFICIENT. Live event baselines: 21 / 98 / 893 (312 insufficient + 581 no facility). Limited contribution cap 14 pts, max observed 9.34, **0 violations**; insufficient / none contribute exactly 0 (**0 violations**).
* New tests (`tests/intelligence/test_baseline_states.py`, 12 tests): 0, 1, 2, 3, 4 historical events → INSUFFICIENT, INSUFFICIENT, LIMITED, LIMITED, ESTABLISHED; zero-history twin contains nothing fabricated; one-event history asserts no normal behaviour; insufficient contributes exactly 0; limited is capped and established is not; no facility ⇒ no facility baseline; limited-history evidence is never STRONG and says so.
* UI: limited history is visibly different from established (dashed muted badge, "— LIMITED HISTORY" in the overall-deviation header, explanatory sentence). Screenshot-verified on EVT-643D746000 (limited baseline, recurrence deviation shown as "SIGNIFICANT DEVIATION — LIMITED HISTORY").

## 5. ML wording changes

Model page retitled "ML evidence"; internal terminology removed (no "synthetic", no "geographic holdout"); the evaluation is labelled "Development-set evaluation (random hold-out)"; per-class table and confusion matrix carry the same label; "development label" replaces "actual". The top bar shows "rf-proxy-v2 · ML evidence". Every ML surface carries: *"ML evidence is one component of OrbiFlare's evidence stack and is not presented as confirmation of a fire."* and *"Evidence sources may be correlated; ML output is treated as one evidence component."*

## 6. ML Model Remediation

**Previous behaviour.** One Random Forest (`rf-proxy-v1`, 7 features) fitted on a generated development corpus with heuristic labels: `CLASS_A if dist_to_facility ≤ 5 km and persistence ≥ 2`, 16 % random label flips, 20–25 % feature noise. Hold-out = rows whose `region_id` is 8 or 9; `region_id` is drawn independently of every feature, so this is a random 20 % row split (the code and UI called it "geographic"). For LOW-quality or absent facility context the model was shown `dist = 50 km`.

**Label/feature overlap discovered (now recorded in `rf_metrics.json`: `label_rule_inputs`, `features_overlapping_label_rule`).**

| Layer | Signals |
|---|---|
| Label generation | `dist_nearest_facility_km`, `persistence_count` |
| Model features | those two **plus** BT, FRP, agri-season, day/night, month (BT and FRP are generated from the same latent "industrial world" flag as the label, so they correlate with it for generation reasons) |
| Downstream risk evidence | separate persistence factor (15 %), duration (15 %), intensity (10 %) and facility-context factor (10 %) — the ML term (15 %) partly restates persistence and facility proximity |

Consequence: the score measures recovery of the labelling rule; ML + facility + persistence are not independent confirmations. Ablations (same corpus/split/settings): without distance macro-F1 0.737; without persistence 0.789; the proxy rule itself scores 0.825 with no learning; label noise ceiling ≈ 0.84.

**The sentinel problem (validation).** 50 km lies in the training range but is sparsely covered (22 / 1,400 rows within 45–55 km) and the forest's response to distance is non-monotone (P(A) at 50 km exceeded P(A) at 10 km). Using it flipped the predicted class of 125 / 347 LOW-quality live events.

**Facility-feature change.** `FeatureVector.facility_context_state ∈ {USABLE, LOW_QUALITY, NONE}`; the distance is `None` unless the state is USABLE (a validator rejects inconsistent combinations). Two models are trained from the **same corpus, split and hyper-parameters** by the existing pipeline (`train_and_evaluate`) and saved alongside each other:

* FULL (7 features) — used only when an identified (High/Medium) facility is nearby;
* NO-FACILITY (6 features, no distance input) — used for LOW-quality or absent context.

**Retraining required?** Yes for the second model (the feature schema differs). The FULL model is the same fit as before (same seed, data, split, settings): its metrics are identical to the last digit. Version `rf-proxy-v1` → `rf-proxy-v2`, `feature_schema_version = 2`. No data was fabricated, no arbitrary distance was used, nothing was tuned.

**Old vs new metrics (development-set, random hold-out, n = 285: 135 class A / 150 class B):**

| | Old v1 (used with the 50 km sentinel for no-facility events) | New FULL (usable facility) | New NO-FACILITY (no usable facility) |
|---|---|---|---|
| Accuracy | 0.811 | 0.811 | 0.740 |
| Balanced accuracy | — (not computed then) | 0.812 | 0.737 |
| Macro-F1 | 0.810 | 0.810 | 0.737 |
| Weighted-F1 | — | 0.811 | 0.739 |
| ROC-AUC | 0.858 | 0.858 | 0.790 |
| Class A P / R / F1 | 0.779 / 0.837 / 0.807 | 0.779 / 0.837 / 0.807 | 0.756 / 0.667 / 0.709 |
| Class B P / R / F1 | 0.843 / 0.787 / 0.814 | 0.843 / 0.787 / 0.814 | 0.729 / 0.807 / 0.766 |
| Confusion matrix (rows = development label A, B) | [[113, 22], [32, 118]] | [[113, 22], [32, 118]] | [[90, 45], [29, 121]] |

The distance-free model scores lower. That is the honest cost of not pretending to know a distance; it is kept.

**What the metrics mean.** Agreement between the model and a heuristic labelling rule, on 285 held-out generated rows. They are **not** real-world fire-detection accuracy, industrial-fire detection accuracy, or an OrbiFlare accuracy figure, and no such figure is given anywhere. The historical backtest remains "not evaluable": validating against the 30 incidents requires archived FIRMS observations matched with independently verified incidents, which the near-real-time ingestion path does not have.

**Facility-context availability behaviour (live).**

| State | Events | Model used | Class label stored on event | ML weight in risk |
|---|---|---|---|---|
| USABLE (High/Medium) | 84 | FULL | yes (39 industrial / 45 natural candidate) | yes (15 %) |
| LOW_QUALITY | 347 | NO-FACILITY | none | 0 |
| NONE | 581 | NO-FACILITY | none | 0 |

**Two consequences I want to be explicit about (found while re-measuring, both intentional).**

1. *Old sentinel behaviour vs new.* Under the sentinel none of the 928 events without usable facility context was ever classed "industrial" (P(A) mean 0.24–0.29). The distance-free model, applied naively, would class 126 of them as industrial (all with ≥ 2 observations), because with no facility information its signal is essentially persistence, which the risk engine already scores. Feeding it in again would double-count the same observations, and in a first measurement it promoted 9 events from LOW to MEDIUM purely through the ML term (+7 pts). So: the facility-blind prediction is displayed as evidence (probabilities, "run without any facility-distance input") but (a) is listed only as uncertain/weak evidence, (b) adds **0** to the risk score, and (c) is not turned into a class label on the event (Events table: "No class (no usable facility)"). Tests: `test_facility_blind_ml_adds_no_weight_to_the_score_and_is_never_supporting_evidence`, `test_facility_blind_prediction_is_not_turned_into_a_class_label_on_the_event`.
2. *Scores moved.* Because the ML term derived from the 50 km sentinel (≈ 4 pts on average) is gone, and the intensity definition is unified, risk changed for 937 / 1,012 events (mean −3.7, max −8.2, never up): MEDIUM events 10 → 5, LOW 1,002 → 1,007, HIGH 0 → 0, maximum risk 44.0 → 44.0. Thresholds were not touched and no HIGH events were forced.

**Remaining ML limitations.** No verified ground truth; labels are a heuristic; the two label inputs are also features; BT/FRP correlate with the label by construction of the development data; live persistence exceeds the training range for 8 events; the distance-free model is weaker (0.737) and has no facility information; the hold-out is random, not spatial; there is no calibration analysis.

**Why ML is evidence, not confirmation.** It cannot set an alert state (tested), carries a 15 % weight only where it saw a real facility, is one of several evidence items marked "correlated with intensity deviation", never emits a confirmed-fire class, and the UI states that it partly restates facility and persistence evidence.

## 7. UI wording changes

* Removed: "AI-based detection and classification of industrial fires" (page metadata → "Industrial thermal-event intelligence from satellite observations."), "Accuracy (holdout)", "geographic holdout", "proxy labels" in the top bar, and every user-visible "synthetic" (badges, tooltips, map legend/popups, filters, KPIs, refresh messages, report labels, demo fixture names, sensor label, API `source`/`dataset`/`data_label` strings, `purity` keys renamed `demo_*`, demo sensor enum value).
* Guarded by `src/lib/wording.test.ts`, which scans all user-facing source and fails on: "synthetic", "geographic hold-out", "AI-based detection", bare accuracy metric/percent, "fire probability" / "facility caused" / "fire at facility" / "future fires" outside denials, and on the Model page missing its "not real-world fire-detection accuracy" framing.

## 8. Repository wording audit

| Term | User-facing (frontend UI) | Internal (code/comments/docs) | Action |
|---|---|---|---|
| synthetic | 0 | 4 frontend comment lines; 23 backend lines (docstrings, log lines, the `Sensor.SYNTHETIC` identifier, `generate_synthetic_training_corpus` which the validation script imports, demo-fixture module); 17 doc lines | user-facing fixed; internal kept (accurate methodology) |
| proxy-label / proxy-labelled | Limitations page and the required ML note (honest disclosure, no "synthetic") | docs, caveats | kept deliberately |
| geographic holdout | 0 | 0 (docs/ml.md and DESIGN_AND_FEATURES.md corrected to "random hold-out") | fixed |
| AI-based detection and classification of industrial fires | 0 | README.md line 3 = the SIH26162 problem-statement title | kept as a quotation of the official title |
| confirmed fire | 10 lines, all denials ("not a confirmed fire") | banned-phrase list in `explanations.py`, docs | verified safe |
| fire probability | 6 lines, all denials | same | verified safe |
| predict future fires | 0 | trajectory docstrings deny it | — |
| facility caused | 1 (Limitations "we never claim…" list) | banned list, docs | safe |
| fire at facility | 0 | 0 | — |

Claim audit (validation script, unmodified): 62 pattern hits, 61 negations/denials, **1 flagged** (README title) vs 7 flagged before.

## 9. Tests, build, validation

| | Before | After |
|---|---|---|
| Backend tests | 237 | **275 passed, 0 failed** (+38: risk/trajectory 8, ML facility-state 18, baseline states 12, plus updated policy tests) |
| Frontend tests | 38 | **51 passed** (+13: wording scan 7, context meaning, limited-history deviation badge/table, insufficient display, ML role/correlation) |
| Typecheck (`tsc --noEmit`) | clean | **clean** |
| Production build | ok | **ok** (MAP_KEY not present in build output) |

Validation re-run (`python scripts/validate_accuracy.py`, unmodified): FIRMS ingestion fidelity 1,346 / 1,346; facility association 1,012 / 1,012; trajectory-vs-event risk **1,012 / 1,012** (was 933); severity-vs-threshold 100 %; limited cap 0 violations; insufficient non-zero deviation 0; LOW-quality facility risk contribution 0; event/pipeline tests 101 / 101; full backend suite 275 / 275; refresh 11.6–12.2 s, idempotent (0 new observations, 0 new events on repeat; batching active).

**Stale text in the regenerated validation report.** Because the script was intentionally not edited, a few hard-coded explanatory sentences in `orbiflare_accuracy_validation.md/.json` describe the *previous* state: the `trajectory_final_point_note` (explains the peak-vs-latest cause that is now fixed), Section E's "Recommendation (NOT applied)" and the LOW-quality "live effect of the sentinel" (it evaluates the old 50 km policy on the script's own model copies), and its distribution-shift block still counts stored classes. The metrics it computes are current; use this report for the interpretation.

**Visual inspection (browser, this pass — succeeded):** Model page (top and middle), Investigation EVT-643D746000 (limited baseline: banner, dashed deviation badges, ML note with "run without any facility-distance input", risk explanation), Investigation EVT-8E5A500939 (no facility: insufficient-baseline table, ML weight explanation, ML shown as weak/uncertain evidence), Command Center, Events. Screenshots were coarse (0.6 scale); Analytics, Thermal Twins, GIS, Reports, Query Console and Limitations were checked in the previous pass and by server-rendered HTML (0 occurrences of "synthetic", "geographic hold-out", "AI-based detection", "81 %") in this pass, not re-screenshotted. The Next dev "1 Issue" badge is a React hydration warning from a browser extension injecting attributes into buttons, not an application error.

## 10. Remaining limitations

* No verified ground truth; no real-world accuracy number exists or is claimed. Historical incident validation: 0 / 30 evaluable (no archive path), reported as "not evaluable", not as a failure.
* Facility association validates the computation, not OSM/GPPD completeness; 347 of 431 associations are Low quality.
* Baselines are limited by ~5 days of stored near-real-time history (4 established / 26 limited / 252 insufficient facility twins). A limited baseline can still show odd values (e.g. a recurrence "typical interval ≈ 0 d"); the UI now qualifies it but the statistic is unchanged.
* Events with no usable facility (928 of 1,012) receive no ML class label and no ML weight, so their priority rests on persistence, duration, intensity and (where present) baseline deviation only.
* `Sensor.SYNTHETIC` (identifier) and `generate_synthetic_training_corpus` keep their names in code; only user-visible strings were changed.
* MAP_KEY rotation is still required externally; the key value in `backend/.env` is unchanged and must be treated as compromised.

## 11. Files changed

Backend: `app/intelligence/{risk,pipeline,trajectory,classification,evidence,investigation}.py`, `app/ingestion/{firms_refresh,demo_fixtures}.py`, `app/model/{ml_schemas,train,predict,schemas}.py`, `app/api/routes/{context,pipeline}.py`, `app/reporting/incident_report.py`; artifacts `data/rf_model.joblib`, `data/rf_model_no_facility.joblib`, `data/rf_metrics.json`.
Backend tests: `tests/intelligence/{test_risk_trajectory_consistency,test_baseline_states}.py` (new), `tests/model/test_ml_facility_state.py` (new), updated `test_evidence_policy.py`, `test_real_data_pipeline.py`, `tests/model/test_ml.py`, `tests/ingestion/{test_firms_refresh,test_live_scientific_hardening,test_stable_events_and_context}.py`, `tests/reference/test_reference_api.py`.
Frontend: `src/lib/{assessment,format,firmsRefresh}.ts`, `src/types/domain.ts`, `src/app/{layout,model/page,analytics/page,command-center/page,events/page,reports/page,investigation/[eventId]/page}.tsx`, `src/components/{DeviationTable,FacilityContextSection,MlEvidenceNote,DemoBadge,MapPanel}.tsx`; tests `src/lib/wording.test.ts` (new), `src/components/investigation.test.tsx`, `src/lib/{dataMode,firmsRefresh,format}.test.ts`.
Docs: `docs/ml.md`, `docs/api.md` (earlier), `docs/demo.md`, `DESIGN_AND_FEATURES.md`. Reports: this file and the regenerated `orbiflare_accuracy_validation.{md,json}`.
