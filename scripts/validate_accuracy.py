"""OrbiFlare automated accuracy & validation run.  Evaluation only: never modifies the production model, thresholds or events.

    python scripts/validate_accuracy.py [--skip-network] [--skip-tests] [--skip-refresh]

Writes reports/orbiflare_accuracy_validation.json (every number below) and reports/orbiflare_accuracy_validation.md.
Every metric carries numerator / denominator / percentage / population / method. There is NO single overall "accuracy" figure:
the available data does not support one (see the report's Limitations section).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import _pathsetup  # noqa: F401  (puts backend/ on sys.path)
import os
os.chdir(Path(__file__).resolve().parent.parent / "backend")   # settings (.env, relative paths) resolve exactly as in the running app
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)

from app.config import get_settings
from app.model.ml_schemas import FEATURE_NAMES
from app.model.train import CLASS_A, CLASS_B, generate_synthetic_training_corpus

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
REPORTS = ROOT / "reports"
DB = BACKEND / "data" / "orbiflare.db"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
S = get_settings()


def metric(name, num, den, population, method, **extra):
    return {"metric": name, "numerator": num, "denominator": den, "percent": (round(100.0 * num / den, 2) if den else None),
            "population": population, "date": NOW, "method": method, **extra}


def db():
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ============================================================================ C/D/E : RF proxy-label evaluation
def _fit(Xtr, ytr):
    return RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42).fit(Xtr, ytr)


def _scores(clf, X, y, cols):
    Xs = X[:, cols]
    pred = clf.predict(Xs)
    proba = clf.predict_proba(Xs)
    a = list(clf.classes_).index(CLASS_A)
    b = 1 - a
    labs = [CLASS_A, CLASS_B]
    p = precision_score(y, pred, labels=labs, average=None, zero_division=0)
    r = recall_score(y, pred, labels=labs, average=None, zero_division=0)
    f = f1_score(y, pred, labels=labs, average=None, zero_division=0)
    ya = (y == CLASS_A).astype(int)
    return {
        "n": int(len(y)), "confusion_matrix": {"labels": labs, "matrix": confusion_matrix(y, pred, labels=labs).tolist()},
        "accuracy": float((pred == y).mean()), "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro")), "weighted_f1": float(f1_score(y, pred, average="weighted")),
        "per_class": {lab: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int((y == lab).sum())} for i, lab in enumerate(labs)},
        "roc_auc": float(roc_auc_score(ya, proba[:, a])),
        "pr_auc_class_A": float(average_precision_score(ya, proba[:, a])), "pr_auc_class_B": float(average_precision_score(1 - ya, proba[:, b])),
        "class_A_prevalence": float(ya.mean()),
    }


def rf_section(events_rows):
    X, y, regions = generate_synthetic_training_corpus()          # exactly as implemented (n=1400, seed=7)
    val = np.isin(regions, [8, 9])
    Xtr, ytr, Xv, yv = X[~val], y[~val], X[val], y[val]
    allc = list(range(len(FEATURE_NAMES)))
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    clf = _fit(Xtr[:, allc], ytr)
    main = _scores(clf, Xv, yv, allc)
    stored = json.loads((BACKEND / "data" / "rf_metrics.json").read_text(encoding="utf-8"))
    repro = {"stored_accuracy": stored["accuracy"], "rerun_accuracy": main["accuracy"], "identical": abs(stored["accuracy"] - main["accuracy"]) < 1e-12,
             "stored_confusion": stored["confusion_matrix"]["matrix"], "rerun_confusion": main["confusion_matrix"]["matrix"],
             "stored_trained_at": stored["trained_at"]}
    # bootstrap CI (validation rows, 2000 resamples) -- sampling uncertainty on n=285 only
    rng = np.random.default_rng(0)
    pred = clf.predict(Xv)
    accs = [float((pred[i] == yv[i]).mean()) for i in (rng.integers(0, len(yv), len(yv)) for _ in range(2000))]
    main["accuracy_bootstrap_95ci"] = [float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))]

    # proxy-rule reference: what the LABEL RULE itself scores on the (noisy) observed features
    rule_pred = np.where((Xv[:, idx["dist_nearest_facility_km"]] <= 5.0) & (Xv[:, idx["persistence_count"]] >= 2), CLASS_A, CLASS_B)
    rule = {"accuracy": float((rule_pred == yv).mean()), "macro_f1": float(f1_score(yv, rule_pred, average="macro")),
            "note": "The proxy LABEL RULE (dist<=5 km AND persistence>=2) applied directly to the observed features. It needs no learning."}
    train_rule_pred = np.where((Xtr[:, idx["dist_nearest_facility_km"]] <= 5.0) & (Xtr[:, idx["persistence_count"]] >= 2), CLASS_A, CLASS_B)
    rule["accuracy_on_training_rows"] = float((train_rule_pred == ytr).mean())

    # ablations (same corpus, same split, same hyper-parameters; evaluation only)
    def ablate(drop):
        cols = [i for i, n in enumerate(FEATURE_NAMES) if n not in drop]
        c = _fit(Xtr[:, cols], ytr)
        s = _scores(c, Xv, yv, cols)
        s["features_used"] = [FEATURE_NAMES[i] for i in cols]
        return s
    ablations = {
        "all_features (production)": {k: main[k] for k in ("accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "roc_auc", "pr_auc_class_A")},
        "without dist_nearest_facility_km": ablate({"dist_nearest_facility_km"}),
        "without persistence_count": ablate({"persistence_count"}),
        "without dist AND persistence (the two label-rule inputs)": ablate({"dist_nearest_facility_km", "persistence_count"}),
        "only dist AND persistence": ablate({n for n in FEATURE_NAMES} - {"dist_nearest_facility_km", "persistence_count"}),
    }
    for k, v in ablations.items():
        if "features_used" in v:
            v["delta_macro_f1_vs_production"] = v["macro_f1"] - main["macro_f1"]
            v["delta_accuracy_vs_production"] = v["accuracy"] - main["accuracy"]
            v["delta_pr_auc_A_vs_production"] = v["pr_auc_class_A"] - main["pr_auc_class_A"]

    # stability of the ablation gap across 20 independently generated corpora (same split rule)
    gaps = []
    for seed in range(100, 120):
        Xs, ys, rs = generate_synthetic_training_corpus(seed=seed)
        v = np.isin(rs, [8, 9])
        full = _fit(Xs[~v], ys[~v])
        cols = [i for i, n in enumerate(FEATURE_NAMES) if n != "dist_nearest_facility_km"]
        nod = _fit(Xs[~v][:, cols], ys[~v])
        f_full = f1_score(ys[v], full.predict(Xs[v]), average="macro")
        f_nod = f1_score(ys[v], nod.predict(Xs[v][:, cols]), average="macro")
        gaps.append((f_full, f_nod))
    g = np.array(gaps)
    stability = {"corpus_seeds": "100..119", "macro_f1_with_dist_mean": float(g[:, 0].mean()), "macro_f1_with_dist_sd": float(g[:, 0].std()),
                 "macro_f1_without_dist_mean": float(g[:, 1].mean()), "macro_f1_without_dist_sd": float(g[:, 1].std()),
                 "mean_drop": float((g[:, 0] - g[:, 1]).mean())}

    perm = permutation_importance(clf, Xv, yv, n_repeats=30, random_state=0, scoring="f1_macro")
    importance = {"impurity_based": {n: float(v) for n, v in zip(FEATURE_NAMES, clf.feature_importances_)},
                  "permutation_macro_f1_drop_on_holdout": {n: float(v) for n, v in zip(FEATURE_NAMES, perm.importances_mean)}}

    # holdout honesty
    holdout = {"split": "regions 8-9 of 10", "n_train": int((~val).sum()), "n_val": int(val.sum()),
               "region_id_definition": "rng.integers(0,10) drawn independently of every feature and label",
               "consequence": "The 'geographic holdout' is a random 20% row split: region_id carries no geography, so it does NOT test spatial generalisation.",
               "data": "Entirely synthetic (generate_synthetic_training_corpus); no real FIRMS observation is used to train or evaluate the RF."}

    # ----- E: 50 km sentinel
    dist = X[:, idx["dist_nearest_facility_km"]]
    cls_a, cls_b = y == CLASS_A, y == CLASS_B

    def pct(a):
        return {f"p{q}": float(np.percentile(a, q)) for q in (0, 1, 5, 25, 50, 75, 95, 99, 100)}
    sent = {"training_distance_all": pct(dist), "training_distance_class_A": pct(dist[cls_a]), "training_distance_class_B": pct(dist[cls_b]),
            "frequency": {
                "rows_with_dist_gt_40": metric("rows dist > 40 km", int((dist > 40).sum()), int(len(dist)), "1,400 synthetic training corpus rows", "count"),
                "rows_with_dist_45_55": metric("rows 45..55 km", int(((dist >= 45) & (dist <= 55)).sum()), int(len(dist)), "training corpus", "count"),
                "class_A_rows_with_dist_ge_45": metric("class A rows dist>=45", int((dist[cls_a] >= 45).sum()), int(cls_a.sum()), "class A rows", "count"),
                "class_B_rows_with_dist_ge_45": metric("class B rows dist>=45", int((dist[cls_b] >= 45).sum()), int(cls_b.sum()), "class B rows", "count"),
                "class_B_rows_45_55": metric("class B rows 45..55", int(((dist[cls_b] >= 45) & (dist[cls_b] <= 55)).sum()), int(cls_b.sum()), "class B rows", "count"),
                "class_A_maximum_distance_km": float(dist[cls_a].max())}}
    full_clf = clf
    live = events_rows
    base_profiles = {}
    if live:
        med = lambda k: float(np.median([r[k] for r in live]))
        base_profiles = {"typical live event (median bt, frp)": dict(bt=med("bt"), frp=med("frp"), pers=1, agri=0.0, dn=0.0, month=9),
                         "persistent live event (persistence 6)": dict(bt=med("bt"), frp=med("frp"), pers=6, agri=0.0, dn=0.0, month=9)}
    else:
        base_profiles = {"nominal": dict(bt=330, frp=10, pers=1, agri=0.0, dn=0.0, month=9)}
    sweep_d = [0.1, 1, 2, 3, 5, 10, 20, 30, 40, 50, 80, 120]
    sweep = {}
    for pname, p in base_profiles.items():
        rows = [[p["bt"], p["frp"], p["pers"], d, p["agri"], p["dn"], p["month"]] for d in sweep_d]
        pa = full_clf.predict_proba(np.array(rows))[:, list(full_clf.classes_).index(CLASS_A)]
        sweep[pname] = {str(d): round(float(v), 4) for d, v in zip(sweep_d, pa)}
    sent["p_class_A_vs_distance_sweep"] = sweep
    sent["p_class_A_at_50_vs_neighbours"] = {n: {"p50": v["50"], "p30": v["30"], "p120": v["120"], "p50_minus_p30": round(v["50"] - v["30"], 4),
                                               "p50_minus_p120": round(v["50"] - v["120"], 4)} for n, v in sweep.items()}
    # live effect: LOW-quality events, actual generic-record distance vs the 50 km sentinel
    low = [r for r in live if r["quality"] == "LOW" and r["dist"] is not None]
    if low:
        def vec(r, d):
            return [r["bt"], r["frp"], r["obs"], d, r["agri"], r["night"], r["month"]]
        ai = list(full_clf.classes_).index(CLASS_A)
        pa_real = full_clf.predict_proba(np.array([vec(r, r["dist"]) for r in low]))[:, ai]
        pa_sent = full_clf.predict_proba(np.array([vec(r, 50.0) for r in low]))[:, ai]
        flips = int(((pa_real >= 0.5) != (pa_sent >= 0.5)).sum())
        sent["live_effect_on_LOW_quality_events"] = {
            "events": len(low), "class_flips_when_using_sentinel": metric("LOW-quality events whose predicted class differs sentinel vs actual generic distance", flips, len(low), "live events with LOW-quality facility context", "predict_proba >= 0.5, everything else identical"),
            "mean_p_A_actual_distance": float(pa_real.mean()), "mean_p_A_sentinel_50km": float(pa_sent.mean()),
            "mean_shift": float((pa_sent - pa_real).mean()), "actual_distance_km_median": float(np.median([r["dist"] for r in low]))}
    noctx = [r for r in live if r["dist"] is None]
    if noctx:
        ai = list(full_clf.classes_).index(CLASS_A)
        def v2(r, d):
            return [r["bt"], r["frp"], r["obs"], d, r["agri"], r["night"], r["month"]]
        sent["live_no_context_events_n"] = len(noctx)
        sent["live_no_context_mean_p_A_at_50"] = float(full_clf.predict_proba(np.array([v2(r, 50.0) for r in noctx]))[:, ai].mean())
        sent["live_no_context_mean_p_A_at_3km_assumed_edge"] = float(full_clf.predict_proba(np.array([v2(r, 3.0) for r in noctx]))[:, ai].mean())
    # sentinel inside the training support?
    inside = float(np.mean(dist[cls_b] >= 45))
    sent["assessment"] = (
        f"50 km is INSIDE the training range (max {dist.max():.1f} km) but sparsely populated: {int((dist>=45).sum())}/{len(dist)} rows lie at >= 45 km "
        f"({int((dist[cls_b]>=45).sum())}/{int(cls_b.sum())} class-B rows, {int((dist[cls_a]>=45).sum())}/{int(cls_a.sum())} class-A rows; the class-A ones are label-noise flips). "
        "The forest's response to distance is NOT monotone (see the sweep: P(A) is lower at 10 km than at 50 km for typical events) because it has few samples in the far tail, so 50 km is read as 'somewhat far', not as a clean 'no facility'. "
        "That is the intended meaning for a LOW-quality generic record, but it is also an ARTIFICIAL classification effect: the true distance is unknown-but-within-search-radius, and the model receives a specific far value. "
        "Recommendation (NOT applied): represent 'no usable facility' as a missing-value indicator (separate binary feature) or train with an explicit no-facility class, instead of a magic distance."
    )
    return {"main": main, "rerun_vs_stored": repro, "proxy_rule_reference": rule, "ablations": ablations, "ablation_stability": stability,
            "importance": importance, "holdout": holdout, "label_noise_ceiling": {"label_flip_probability": 0.16, "approx_max_accuracy_vs_proxy_labels": 0.84,
            "note": "16% of proxy labels are flipped at random by construction, so no model can score much above ~84% accuracy against them."}}, sent


# ============================================================================ live events & distribution shift
def load_live_events():
    c = db()
    rows = []
    for r in c.execute("select * from events where is_demo=0"):
        fd = datetime.fromisoformat(str(r["first_detected"]))
        hour, month = fd.hour, fd.month
        rows.append({"id": r["event_id"], "bt": r["peak_bt"] or r["mean_bt"] or 300.0, "frp": r["peak_frp"] or r["mean_frp"] or 5.0, "obs": float(r["observation_count"]),
                     "dist": r["facility_distance_km"], "quality": r["facility_context_quality"], "agri": 1.0 if month in {4, 5, 10, 11} else 0.0,
                     "night": 1.0 if (hour >= 18 or hour < 6) else 0.0, "month": float(month), "risk": r["risk_score"], "sev": r["severity"],
                     "traj": r["trajectory_direction"], "cls": r["classification"], "lat": r["centroid_lat"], "lon": r["centroid_lon"], "fac": r["facility_id"],
                     "first": r["first_detected"], "status": r["status"], "pers": r["observation_count"]})
    return rows


def shift_section(rows, X):
    if not rows:
        return {}
    tr = {"persistence_max": float(X[:, 2].max()), "frp_max": float(X[:, 1].max()), "bt_max": float(X[:, 0].max()), "bt_min": float(X[:, 0].min()), "frp_min": float(X[:, 1].min())}
    n = len(rows)
    return {"note": "Share of LIVE events whose feature lies outside the range the RF saw in training (synthetic corpus).",
            "persistence_gt_training_max": metric("live events with persistence > training max", sum(r["obs"] > tr["persistence_max"] for r in rows), n, "live events", f"training max persistence = {tr['persistence_max']:.0f}"),
            "frp_gt_training_max": metric("live events with FRP > training max", sum(r["frp"] > tr["frp_max"] for r in rows), n, "live events", f"training max FRP = {tr['frp_max']:.0f}"),
            "bt_outside_training": metric("live events with BT outside training range", sum((r["bt"] > tr["bt_max"] or r["bt"] < tr["bt_min"]) for r in rows), n, "live events", f"training BT range {tr['bt_min']:.0f}..{tr['bt_max']:.0f} K"),
            "live_feature_summary": {k: {"min": float(np.min([r[k] for r in rows])), "median": float(np.median([r[k] for r in rows])), "max": float(np.max([r[k] for r in rows]))} for k in ("bt", "frp", "obs")},
            "live_predicted_class_counts": dict(Counter(r["cls"] for r in rows))}


# ============================================================================ F : historical incident backtest
def backtest_section():
    inc = pd.read_csv(ROOT / "data" / "reference" / "incidents" / "confirmed_incidents_india.csv")
    c = db()
    lo, hi = c.execute("select min(timestamp), max(timestamp) from observations").fetchone()
    raw_path = ROOT / "data" / "raw" / "firms_observations.parquet"
    raw = {}
    if raw_path.exists():
        rp = pd.read_parquet(raw_path)
        tcol = next((k for k in rp.columns if "time" in k or "date" in k), None)
        raw = {"path": "data/raw/firms_observations.parquet", "rows": int(len(rp)), "columns": list(rp.columns)[:12]}
        if tcol is not None:
            raw["time_range"] = [str(rp[tcol].min()), str(rp[tcol].max())]
    dates = pd.to_datetime(inc["date"])
    lo_d, hi_d = pd.Timestamp(lo), pd.Timestamp(hi)
    per = []
    for _, r in inc.iterrows():
        d = pd.Timestamp(r["date"])
        near = c.execute("select count(*) from observations where timestamp between ? and ? and abs(latitude-?)<0.1 and abs(longitude-?)<0.1",
                         (str(d - pd.Timedelta(days=3)), str(d + pd.Timedelta(days=4)), r["lat"], r["lon"])).fetchone()[0]
        per.append({"incident_id": r["incident_id"], "date": r["date"], "name": r["name"], "facility_type": r["facility_type"],
                    "date_inside_stored_firms_window": bool(lo_d <= d <= hi_d), "stored_observations_within_0.1deg_and_-3/+4d": int(near)})
    evaluable = [p for p in per if p["date_inside_stored_firms_window"]]
    firms_code = (BACKEND / "app" / "ingestion" / "firms.py").read_text(encoding="utf-8") + (BACKEND / "app" / "ingestion" / "firms_refresh.py").read_text(encoding="utf-8")
    mechanism = {"live_api_products": [p for p in re.findall(r"VIIRS_[A-Z0-9_]+_(?:NRT|SP)|MODIS_(?:NRT|SP)", firms_code)][:6],
                 "archive_product_supported": bool(re.search(r"_SP\b", firms_code)),
                 "local_csv_ingest": "ingest_from_local_file() accepts an analyst-supplied FIRMS CSV (no such CSV for 2019-2023 exists in the repo)",
                 "conclusion": "The project ingests NEAR-REAL-TIME data only (day_range <= 5 from today). It has no historical/archive acquisition mechanism."}
    n = len(inc)
    return {"title": "HISTORICAL INCIDENT BACKTEST", "incidents_total": n, "incident_date_range": [str(dates.min().date()), str(dates.max().date())],
            "stored_firms_window": [str(lo), str(hi)], "raw_parquet": raw, "acquisition_mechanism": mechanism,
            "incidents_evaluable": metric("incidents with FIRMS coverage for their date", len(evaluable), n, "30 curated historical incidents (2019-2023)", "incident date inside the stored FIRMS observation window"),
            "incidents_not_evaluable_missing_coverage": metric("incidents without FIRMS coverage", n - len(evaluable), n, "same", "same; NOT counted as model failures"),
            "incidents_with_nearby_firms_observations": metric("incidents with stored observations within 0.1 deg and -3/+4 days", sum(p["stored_observations_within_0.1deg_and_-3/+4d"] > 0 for p in per), n, "same", "SQL count"),
            "incidents_surfaced_as_events": None, "capture_rate": None, "top10pct_capture": None, "top25pct_capture": None, "median_rank": None,
            "why_no_capture_metrics": "No incident has FIRMS coverage, so there is nothing to process, surface or rank. No historical observation was invented and no incident was manually labelled.",
            "incident_suitability_notes": "Even with archive data, several of the 30 records are not thermal-anomaly targets at VIIRS scale or are not fires (gas leak, memorial anniversary, stubble-burning reference points, chronic thermal sources), and coordinates are approximate (site/city level).",
            "what_would_be_needed": "A FIRMS archive extract (Standard Processing, e.g. VIIRS SNPP/NOAA-20 for 2019-2023) for each incident date +/- a few days over India, ingested with the existing local-CSV path and run through the existing event logic. Not done here.",
            "per_incident": per}


# ============================================================================ B : facility association recomputation
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def facility_section(rows):
    df = pd.read_parquet(ROOT / "data" / "facilities" / "osm_gppd_facilities.parquet")
    df = df[df["lat"].between(6, 37) & df["lon"].between(68, 98) & ~df["facility_type"].isin({"Solar", "Wind", "Hydro"})].reset_index(drop=True)
    lat, lon, fid = df["lat"].to_numpy(), df["lon"].to_numpy(), df["facility_id"].to_numpy()
    rad = S.facility_context_radius_km
    exact = wrong_id = wrong_dist = missing = spurious = 0
    bad = []
    for r in rows:
        d = haversine_km(r["lat"], r["lon"], lat, lon)          # brute force over every indexed facility (independent of the BallTree)
        j = int(np.argmin(d))
        exp_id, exp_d = (fid[j], float(d[j])) if d[j] <= rad else (None, None)
        got_id, got_d = r["fac"], r["dist"]
        if exp_id is None and got_id is None:
            exact += 1
        elif exp_id is None:
            spurious += 1; bad.append((r["id"], "stored facility but none within radius", got_id))
        elif got_id is None:
            missing += 1; bad.append((r["id"], "facility within radius not stored", exp_id))
        elif exp_id == got_id and abs(exp_d - got_d) < 0.02:
            exact += 1
        elif exp_id != got_id:
            wrong_id += 1; bad.append((r["id"], "different nearest facility", (exp_id, got_id)))
        else:
            wrong_dist += 1; bad.append((r["id"], "distance differs", (exp_d, got_d)))
    n = len(rows)
    with_ctx = sum(1 for r in rows if r["fac"])
    return {"note": "Spatial association only. Says nothing about causation.", "indexed_facilities": int(len(df)), "radius_km": rad,
            "events_tested": n, "exact_matches": metric("events whose stored facility association equals the independent recomputation", exact, n, "all live events", "brute-force haversine to every indexed facility (numpy), nearest within radius; id equal and distance within 0.02 km; 'none' must also match"),
            "events_with_context": with_ctx, "mismatches": {"wrong_facility": wrong_id, "wrong_distance": wrong_dist, "context_missing": missing, "context_spurious": spurious}, "mismatch_examples": [list(map(str, b)) for b in bad[:10]],
            "quality_counts_events": dict(Counter(r["quality"] for r in rows if r["fac"]))}


# ============================================================================ A : FIRMS ingestion fidelity (independent re-parse of a fresh NASA response)
def firms_fidelity():
    import httpx
    if not S.firms_map_key:
        return {"skipped": "no MAP_KEY configured"}
    c = db()
    out = {"note": "Independent csv-module parse of a fresh NASA response, compared to the stored rows. Ingestion fidelity, NOT accuracy of fire detection.", "products": {}}
    tot = exact = mism = missing = 0
    field_bad = Counter()
    for prod in S.firms_source_list:
        url = f"{S.firms_api_base}/{S.firms_map_key}/{prod}/{S.firms_bbox}/{S.firms_day_range}"
        try:
            text = httpx.get(url, timeout=S.firms_timeout_s).text
        except Exception:                                   # never echo httpx text: it contains the URL (and the key)
            out["products"][prod] = {"error": "request failed (details withheld: URL contains the key)"}
            continue
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "latitude" not in rows[0]:
            out["products"][prod] = {"error": "unexpected response body"}
            continue
        stored = {}
        for r in c.execute("select * from observations where source_product=?", (prod,)):
            ts = str(r["timestamp"])[:16]
            stored[(round(r["latitude"], 5), round(r["longitude"], 5), ts)] = r
        pe = pm = pmiss = 0
        for row in rows:
            t = str(int(row["acq_time"])).zfill(4)
            key = (round(float(row["latitude"]), 5), round(float(row["longitude"]), 5), f"{row['acq_date']} {t[:2]}:{t[2:]}")
            s = stored.get(key)
            if s is None:
                pmiss += 1
                continue
            checks = {"frp": (float(row["frp"]), s["frp"]), "bright_ti4": (float(row["bright_ti4"]), s["brightness_temperature"]),
                      "bright_ti5": (float(row["bright_ti5"]), s["brightness_temperature_11"]), "scan": (float(row["scan"]), s["scan"]),
                      "track": (float(row["track"]), s["track"])}
            ok = all(b is not None and abs(a - b) < 1e-6 for a, b in checks.values())
            ok &= (str(row["confidence"]) == str(s["confidence"])) and (row["daynight"] == s["day_night"]) and (row["satellite"] == s["satellite"])
            for k, (a, b) in checks.items():
                if b is None or abs(a - b) >= 1e-6:
                    field_bad[k] += 1
            if str(row["confidence"]) != str(s["confidence"]): field_bad["confidence"] += 1
            if row["daynight"] != s["day_night"]: field_bad["daynight"] += 1
            if row["satellite"] != s["satellite"]: field_bad["satellite"] += 1
            pe += ok
            pm += (not ok)
        out["products"][prod] = {"rows_from_nasa_now": len(rows), "exact": pe, "field_mismatch": pm, "not_in_database": pmiss}
        tot += len(rows); exact += pe; mism += pm; missing += pmiss
    out["observations_checked"] = tot
    out["exact_matches"] = metric("NASA rows reproduced exactly in the database (lat, lon, time, satellite, FRP, BT4, BT5, confidence, day/night, scan, track)", exact, tot, "rows NASA returns right now for the configured products/window", "csv-module parse vs stored row")
    out["field_mismatch_counts"] = dict(field_bad)
    out["not_in_database"] = missing
    out["extra_note"] = "'not_in_database' rows are detections NASA published after the last refresh; they are not ingestion errors."
    return out


# ============================================================================ G : event-engine tests
def run_pytest(paths, tag):
    xml = REPORTS / f"_junit_{tag}.xml"
    p = subprocess.run([sys.executable, "-m", "pytest", *paths, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", "-W", "ignore"], cwd=BACKEND, capture_output=True, text=True)
    cases = []
    for tc in ET.parse(xml).getroot().iter("testcase"):
        st = "pass"
        for ch in tc:
            if ch.tag in ("failure", "error"): st = "fail"
            elif ch.tag == "skipped": st = "skip"
        cases.append((tc.get("classname", "") + "::" + tc.get("name", ""), st))
    xml.unlink(missing_ok=True)
    return cases, p.returncode


CATS = {
    "growth keeps the same event ID": r"grow|extend|stable_id|keeps_id|same_id|identity",
    "unrelated activity gets a separate ID": r"unrelated|separate",
    "refresh does not duplicate (idempotent)": r"idempot|duplicate|second_refresh|no_duplicate|repeat",
    "merge is audited": r"merge",
    "split is audited": r"split",
    "operator state preserved": r"operator|lifecycle|state_pres|alert_state|acknowledg",
    "trajectory consistent/preserved": r"trajectory",
}


def tests_section(skip):
    if skip:
        return {"skipped": True}
    cases, rc = run_pytest(["tests"], "all")
    tot = Counter(s for _, s in cases)
    ev_files = ("test_stable_events_and_context", "test_live_scientific_hardening", "test_firms_refresh", "test_events", "test_trajectory", "test_lifecycle", "test_pipeline_integration", "test_real_data_pipeline", "test_evidence_policy")
    ev_cases = [(n, s) for n, s in cases if any(f in n for f in ev_files)]
    cats = {}
    for cat, pat in CATS.items():
        sel = [(n, s) for n, s in ev_cases if re.search(pat, n.split("::")[-1], re.I)]
        cats[cat] = {"tests": len(sel), "passed": sum(s == "pass" for _, s in sel), "failed": sum(s == "fail" for _, s in sel), "names": [n.split("::")[-1] for n, _ in sel]}
    return {"full_backend_suite": {"total": len(cases), "passed": tot["pass"], "failed": tot["fail"], "skipped": tot["skip"], "exit_code": rc},
            "event_and_pipeline_test_files": {"tests": len(ev_cases), "passed": sum(s == "pass" for _, s in ev_cases), "failed": sum(s == "fail" for _, s in ev_cases)},
            "by_behaviour": cats, "failed_tests": [n for n, s in cases if s == "fail"]}


# ============================================================================ H : risk / replay consistency on the live DB
def risk_section():
    c = db()
    n = c.execute("select count(*) from events where is_demo=0").fetchone()[0]
    tm, th, tc_ = S.risk_threshold_medium, S.risk_threshold_high, S.risk_threshold_critical
    def sev(x):
        return "CRITICAL" if x >= tc_ else "HIGH" if x >= th else "MEDIUM" if x >= tm else "LOW"
    sev_ok = sum(1 for r in c.execute("select risk_score, severity from events where is_demo=0") if r[0] is not None and sev(r[0]) == r[1])
    stored_ok = last_ok = mono_ok = with_pts = in_range = 0
    cap_bad = ins_bad = lowfac_bad = 0
    lim_n = ins_n = est_n = 0
    max_lim = 0.0
    q = {r[0]: r[1] for r in c.execute("select event_id, facility_context_quality from events")}
    for r in c.execute("select r.event_id, r.risk_score, r.payload, e.risk_score from risk_assessments r join events e using(event_id) where e.is_demo=0"):
        p = json.loads(r[2])
        stored_ok += (abs(r[1] - r[3]) < 1e-9)
        in_range += (0 <= r[1] <= 100)
        b, d = p.get("baseline_status"), p.get("deviation_contribution") or 0
        if b == "LIMITED":
            lim_n += 1; max_lim = max(max_lim, d); cap_bad += d > S.risk_limited_baseline_factor * 35 + 1e-6
        elif b == "ESTABLISHED": est_n += 1
        else:
            ins_n += 1; ins_bad += d > 0
        if q.get(r[0]) == "LOW":
            lowfac_bad += any(f["name"].startswith("facility") and f["contribution"] > 0 for f in p.get("risk_factors", []))
    for (eid,) in c.execute("select event_id from events where is_demo=0"):
        pts = c.execute("select timestamp, risk_score from risk_trajectory_points where event_id=? order by timestamp", (eid,)).fetchall()
        if not pts: continue
        with_pts += 1
        er = c.execute("select risk_score from events where event_id=?", (eid,)).fetchone()[0]
        last_ok += (er is not None and abs(pts[-1][1] - er) < 0.06)
        mono_ok += all(pts[i][0] <= pts[i + 1][0] for i in range(len(pts) - 1))
    return {"population": "live (non-demo) events in the primary database",
            "severity_matches_thresholds": metric("events whose severity equals the threshold mapping of their score (35/60/80)", sev_ok, n, "live events", "recomputed from config thresholds"),
            "stored_risk_equals_event_risk": metric("risk_assessments.risk_score == events.risk_score", stored_ok, n, "live events", "SQL join"),
            "risk_in_0_100": metric("risk score within [0,100]", in_range, n, "live events", "range check"),
            "trajectory_final_point_equals_event_risk": metric("events whose last trajectory point equals the stored risk (+/-0.06)", last_ok, with_pts, "live events with trajectory points", "SQL"),
            "trajectory_timestamps_monotone": metric("events with non-decreasing trajectory timestamps", mono_ok, with_pts, "live events with trajectory points", "SQL"),
            "limited_baseline_cap": {"events": lim_n, "cap_pts": S.risk_limited_baseline_factor * 35, "max_observed": max_lim, "violations": int(cap_bad)},
            "established_baseline_events": est_n, "insufficient_or_no_baseline_events": ins_n, "insufficient_nonzero_deviation_violations": int(ins_bad),
            "low_quality_facility_with_risk_contribution_violations": int(lowfac_bad),
            "thresholds": {"medium": tm, "high": th, "critical": tc_, "changed_in_this_pass": False}}


# ============================================================================ I : live statistics (+ refresh timing / idempotence)
def live_section(rows, do_refresh):
    import urllib.request as u
    c = db()
    q = lambda s, *a: c.execute(s, a).fetchall()
    obs_total = q("select count(*) from observations where source='FIRMS'")[0][0]
    out = {"note": "Operational statistics. NOT accuracy.", "firms_observations": obs_total,
           "by_satellite": {str(r[0]): r[1] for r in q("select satellite, count(*) from observations group by 1")},
           "acquisition_range_utc": list(q("select min(timestamp), max(timestamp) from observations")[0]),
           "nasa_confidence": {str(r[0]): r[1] for r in q("select confidence, count(*) from observations group by 1")},
           "synthetic_observations": q("select count(*) from observations where source!='FIRMS'")[0][0], "synthetic_events": q("select count(*) from events where is_demo=1")[0][0],
           "events": len(rows), "severity": dict(Counter(r["sev"] for r in rows)), "trajectory": dict(Counter(r["traj"] for r in rows)),
           "escalating": sum(r["traj"] == "ESCALATING" for r in rows), "persistent_ge6_obs": sum(r["obs"] >= 6 for r in rows),
           "status": dict(Counter(r["status"] for r in rows)), "max_risk": max((r["risk"] or 0) for r in rows) if rows else None,
           "facility_context_events": sum(1 for r in rows if r["fac"]), "context_quality": dict(Counter(r["quality"] for r in rows if r["fac"])),
           "events_no_facility_context": sum(1 for r in rows if not r["fac"]), "referenced_facilities": q("select count(*) from facilities")[0][0]}
    tw = Counter(r[0] for r in q("select baseline_confidence from thermal_twins"))
    out["facility_twins"] = dict(tw)
    base = Counter()
    for r in q("select payload from risk_assessments"):
        base[json.loads(r[0]).get("baseline_status") or "NO_FACILITY_CONTEXT"] += 1
    out["event_baselines_from_risk"] = dict(base)
    if do_refresh:
        try:
            def post():
                t = time.time()
                req = u.Request("http://localhost:8000/api/firms/refresh", method="POST")
                d = json.load(u.urlopen(req, timeout=600))
                return d, round(time.time() - t, 1)
            d1, t1 = post()
            d2, t2 = post()
            keep = ("status", "observations_received", "new_observations", "updated_observations", "events_total", "events_created", "events_updated", "events_unchanged", "events_merged", "events_split")
            out["refresh"] = {"first": {**{k: d1.get(k) for k in keep}, "seconds": t1}, "immediately_after": {**{k: d2.get(k) for k in keep}, "seconds": t2},
                              "idempotent": d2.get("new_observations") == 0 and d2.get("events_created") == 0}
        except Exception as e:                              # backend not running / busy
            out["refresh"] = {"skipped": f"backend refresh unavailable ({type(e).__name__})"}
    return out


# ============================================================================ J : scientific claim audit
PATTERNS = [
    ("accuracy percentage", r"\b\d{2}(\.\d+)?\s*%\s*(accura|precision|recall)|accuracy of \d", "Remove; report the proxy-label metric with its population instead."),
    ("fire probability", r"fire[\s_-]*probabilit|probability of (a )?fire", "Use 'operational priority score' / 'thermal-source class probability (proxy-labelled)'."),
    ("confirmed fire", r"confirmed[\s_-]*fires?", "FIRMS detections are 'thermal observations'; only a denial ('not a confirmed fire') is acceptable."),
    ("causation from proximity", r"caused by|caused the|causing the|cause of the|because of (the )?(nearby )?facility|due to (the )?(nearby )?facility", "Use 'spatially associated with' / 'near'."),
    ("industrial fire detected", r"industrial fires? (was |is |were )?(detect|identif)|detects? industrial fire|detected industrial fire", "Use 'persistent industrial thermal-source class (proxy-labelled)'."),
    ("AI predicts fire", r"AI[\s-]+predict|predicts? (a |the )?fires?\b|fire prediction|predict(ing|ion of) fires?", "Use 'prioritises thermal observations for analyst review'."),
    ("AI detection claim", r"AI[- ]based|AI[- ]powered|AI[- ]driven|AI detect", "Describe as an analyst console that prioritises thermal observations; do not claim AI fire detection."),
    ("geographic holdout", r"geographic[_ ]holdout|geographic holdout", "The split is a random row split (region_id is not spatial): call it 'random hold-out' or 'hold-out by synthetic region id'."),
    ("bare accuracy KPI", r"[\"'>]Accuracy \(", "Label as 'Agreement with proxy labels (synthetic hold-out)'; never a bare 'Accuracy'."),
    ("independent confirmation", r"independent(ly)? (confirm|evidence|verif|corrobor)", "Only acceptable when denying independence."),
]
SAFE_LINE = re.compile(r"✗|^\s*\"[a-z ]+\",?|^\s*- \"|missing\.append|double-count|banned|BANNED|FORBIDDEN|_PHRASES|NEVER_CAUSATION|operational prioritization only|\"confirmed fire\", \"detected a fire\"")
DENIAL = re.compile(r"\b(not|no|never|n't|nor|without|absen|cannot|isn't|does not|do not|neither|rather than|instead of|unverified|un-?confirmed)\b|reject|forbid|ban|must not|should not", re.I)


def claim_audit():
    roots = [ROOT / "frontend" / "src", BACKEND / "app", ROOT / "README.md", ROOT / "docs", ROOT / "DESIGN_AND_FEATURES.md"]
    files = []
    for r in roots:
        files += [r] if r.is_file() else [p for p in r.rglob("*") if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".md", ".css"}]
    files = [p for p in files if "node_modules" not in p.parts and ".next" not in p.parts and "__pycache__" not in p.parts and not p.name.endswith(".test.tsx") and not p.name.endswith(".test.ts")]
    hits = []
    for p in files:
        prev = ""
        for ln, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for name, pat, rec in PATTERNS:
                if re.search(pat, line, re.I):
                    hits.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"), "line": ln, "pattern": name, "text": line.strip()[:220],
                                 "context": "DENIAL/NEGATED (safe)" if (DENIAL.search(line) or SAFE_LINE.search(line) or (ln > 1 and DENIAL.search(prev))) else "REVIEW", "recommended": ("Official SIH26162 problem-statement title; acceptable only when quoted as the title. Describe the implemented system precisely (analyst console prioritising FIRMS thermal observations) in the surrounding text." if (p.name == "README.md" and name == "AI detection claim") else rec)})
            prev = line
    return {"files_scanned": len(files), "patterns": [n for n, _, _ in PATTERNS], "hits_total": len(hits), "hits_safe_denial": sum(h["context"].startswith("DENIAL") for h in hits),
            "hits_review": [h for h in hits if h["context"] == "REVIEW"], "safe_denials_sample": [h for h in hits if h["context"].startswith("DENIAL")][:15]}


# ============================================================================ markdown
def fmt(m):
    if isinstance(m, dict) and "numerator" in m:
        return f"{m['numerator']} / {m['denominator']} = {m['percent']}%  _(population: {m['population']}; method: {m['method']})_"
    return str(m)


def write_md(R):
    L = []
    a = L.append
    rf, sent = R["rf"], R["sentinel"]
    m = rf["main"]
    a("# OrbiFlare Accuracy & Validation Report\n")
    a(f"_Generated {NOW} by `scripts/validate_accuracy.py`. Evaluation only: production model, thresholds and events were not modified._\n")
    a("## Executive Summary\n")
    a("**There is no defensible overall real-world accuracy figure for OrbiFlare, and none is reported.** No verified ground truth exists: the RF is trained and scored on synthetic, proxy-labelled data, and none of the 30 historical incidents can be evaluated because no FIRMS data for their dates is available. What *has* been validated is engineering fidelity:\n")
    a(f"- FIRMS ingestion fidelity: {fmt(R['firms_fidelity'].get('exact_matches', 'skipped'))}")
    a(f"- Facility association recomputation: {fmt(R['facility']['exact_matches'])}")
    a(f"- RF vs proxy labels (synthetic, held-out 20%): accuracy {m['accuracy']:.3f}, macro-F1 {m['macro_f1']:.3f}, balanced accuracy {m['balanced_accuracy']:.3f}. This measures recovery of the labelling heuristic, not fire detection.")
    ab = rf["ablations"]["without dist_nearest_facility_km"]
    a(f"- Removing the facility-distance feature changes macro-F1 by {ab['delta_macro_f1_vs_production']:+.3f} (mean over 20 corpora: {-rf['ablation_stability']['mean_drop']:+.3f}).")
    a(f"- Historical backtest: {fmt(R['backtest']['incidents_evaluable'])} evaluable.")
    if "full_backend_suite" in R["tests"]:
        t = R["tests"]["full_backend_suite"]
        a(f"- Backend tests: {t['passed']} passed, {t['failed']} failed, {t['skipped']} skipped (of {t['total']}).")
    a("")
    a("## A. FIRMS Ingestion Fidelity\n")
    f = R["firms_fidelity"]
    if "exact_matches" in f:
        a(f"Not an accuracy claim. {fmt(f['exact_matches'])}\n")
        a(f"- Observations checked: {f['observations_checked']}; not yet in the database (published after last refresh): {f['not_in_database']}; field mismatches: {f['field_mismatch_counts'] or 'none'}")
        for k, v in f["products"].items():
            a(f"- `{k}`: {v}")
    else:
        a(str(f))
    a("\n## B. Facility Association Validation\n")
    fa = R["facility"]
    a(f"Spatial association only, not causation. {fmt(fa['exact_matches'])}\n")
    a(f"- Indexed facilities: {fa['indexed_facilities']:,}; radius {fa['radius_km']} km; events with context: {fa['events_with_context']}; mismatches: {fa['mismatches']}; context quality (events): {fa['quality_counts_events']}")
    a("\n## C. RF Proxy-Label Evaluation\n")
    a("**PROXY-LABEL DEVELOPMENT EVALUATION. Not real-world fire accuracy, not industrial-fire detection accuracy, not fire prediction accuracy.**\n")
    a("- Class A = persistent industrial thermal source; Class B = natural/agricultural fire *candidate*.")
    a("- Population: 285 held-out rows of a 1,400-row **synthetic** corpus (no real FIRMS observation is used). Proxy label = `CLASS_A if dist_to_facility <= 5 km and persistence >= 2`, then 16% random label flips.")
    a("- **The proxy label is built from facility proximity, and facility distance is also a model feature (and persistence is both label input and feature).** The evaluation is therefore partly circular.")
    a(f"- Holdout: {rf['holdout']['consequence']}")
    a(f"- Reproduction check: stored metrics (trained {rf['rerun_vs_stored']['stored_trained_at']}) vs re-run: identical = {rf['rerun_vs_stored']['identical']}\n")
    a("| | Class A precision | recall | F1 | support | Class B precision | recall | F1 | support |\n|---|---|---|---|---|---|---|---|---|")
    pa, pb = m["per_class"][CLASS_A], m["per_class"][CLASS_B]
    a(f"| RF | {pa['precision']:.3f} | {pa['recall']:.3f} | {pa['f1']:.3f} | {pa['support']} | {pb['precision']:.3f} | {pb['recall']:.3f} | {pb['f1']:.3f} | {pb['support']} |\n")
    cm = m["confusion_matrix"]["matrix"]
    a(f"Confusion matrix (rows = proxy label A,B; columns = predicted A,B): `{cm}`\n")
    a(f"- accuracy {m['accuracy']:.3f} (bootstrap 95% CI {m['accuracy_bootstrap_95ci'][0]:.3f}-{m['accuracy_bootstrap_95ci'][1]:.3f}, n={m['n']}), balanced accuracy {m['balanced_accuracy']:.3f}, macro-F1 {m['macro_f1']:.3f}, weighted-F1 {m['weighted_f1']:.3f}")
    a(f"- ROC-AUC {m['roc_auc']:.3f}; PR-AUC class A {m['pr_auc_class_A']:.3f} (prevalence {m['class_A_prevalence']:.3f}); PR-AUC class B {m['pr_auc_class_B']:.3f}")
    r = rf["proxy_rule_reference"]
    a(f"- Reference: the proxy rule itself applied to the observed features scores accuracy {r['accuracy']:.3f} (macro-F1 {r['macro_f1']:.3f}) with no learning; label-noise ceiling is ~{rf['label_noise_ceiling']['approx_max_accuracy_vs_proxy_labels']:.2f}. The RF is essentially re-learning the rule.")
    a("\n## D. Facility-Distance Ablation\n")
    a("Same corpus, split and hyper-parameters; evaluation only.\n")
    a("| Features | accuracy | macro-F1 | balanced acc | PR-AUC A | dMacro-F1 vs production |\n|---|---|---|---|---|---|")
    for k, v in rf["ablations"].items():
        a(f"| {k} | {v['accuracy']:.3f} | {v['macro_f1']:.3f} | {v['balanced_accuracy']:.3f} | {v['pr_auc_class_A']:.3f} | {v.get('delta_macro_f1_vs_production', 0):+.3f} |")
    s = rf["ablation_stability"]
    a(f"\n- Across 20 independently generated corpora ({s['corpus_seeds']}): macro-F1 with distance {s['macro_f1_with_dist_mean']:.3f} +/- {s['macro_f1_with_dist_sd']:.3f}; without {s['macro_f1_without_dist_mean']:.3f} +/- {s['macro_f1_without_dist_sd']:.3f}; mean drop {s['mean_drop']:.3f}.")
    imp = rf["importance"]
    a(f"- Impurity importance: {json.dumps({k: round(v, 3) for k, v in imp['impurity_based'].items()})}")
    a(f"- Permutation importance (macro-F1 drop on holdout): {json.dumps({k: round(v, 3) for k, v in imp['permutation_macro_f1_drop_on_holdout'].items()})}")
    a("- Interpretation: see `interpretation` below.\n")
    a(f"**Interpretation:** {R['ablation_interpretation']}\n")
    a("## E. 50 km Sentinel Analysis\n")
    a(f"- Training distance percentiles (all): {json.dumps({k: round(v, 2) for k, v in sent['training_distance_all'].items()})}")
    a(f"- Class A: {json.dumps({k: round(v, 2) for k, v in sent['training_distance_class_A'].items()})}")
    a(f"- Class B: {json.dumps({k: round(v, 2) for k, v in sent['training_distance_class_B'].items()})}")
    for k, v in sent["frequency"].items():
        a(f"- {fmt(v) if isinstance(v, dict) else k + ': ' + str(v)}")
    a(f"- P(class A) as distance varies (other features fixed): `{json.dumps(sent['p_class_A_vs_distance_sweep'])}`")
    if "live_effect_on_LOW_quality_events" in sent:
        le = sent["live_effect_on_LOW_quality_events"]
        a(f"- Live LOW-quality events ({le['events']}): {fmt(le['class_flips_when_using_sentinel'])}; mean P(A) with actual generic-record distance {le['mean_p_A_actual_distance']:.3f} vs sentinel {le['mean_p_A_sentinel_50km']:.3f} (shift {le['mean_shift']:+.3f})")
    a(f"\n**Assessment:** {sent['assessment']}\n")
    a("## F. Historical Incident Backtest\n")
    b = R["backtest"]
    a(f"- {fmt(b['incidents_evaluable'])}\n- {fmt(b['incidents_not_evaluable_missing_coverage'])}\n- {fmt(b['incidents_with_nearby_firms_observations'])}")
    a(f"- Incident dates {b['incident_date_range']}; stored FIRMS window {b['stored_firms_window']}; raw parquet: {b['raw_parquet']}")
    a(f"- Acquisition mechanism: {b['acquisition_mechanism']['conclusion']}")
    a(f"- Surfaced as events / capture rate / top-10% / top-25% / median rank: **not computable** ({b['why_no_capture_metrics']})")
    a(f"- {b['incident_suitability_notes']}\n- Needed: {b['what_would_be_needed']}\n")
    a("## G. Event Formation Validation\n")
    t = R["tests"]
    if t.get("skipped"):
        a("Skipped.")
    else:
        e = t["event_and_pipeline_test_files"]
        a(f"Event/pipeline/lifecycle test files: {e['passed']} passed, {e['failed']} failed of {e['tests']}. Full backend suite: {t['full_backend_suite']}\n")
        a("| Behaviour | tests | passed | failed |\n|---|---|---|---|")
        for k, v in t["by_behaviour"].items():
            a(f"| {k} | {v['tests']} | {v['passed']} | {v['failed']} |")
        a("\n(Categories are matched by test name; a test can appear in more than one row.)")
        live_note = R["live"].get("refresh")
        if live_note and "first" in live_note:
            a(f"\nLive: refresh idempotent = {live_note['idempotent']}; merged/split in the real refresh: {live_note['first']['events_merged']}/{live_note['first']['events_split']} (merge/split are exercised only by tests).")
    a("\n## H. Risk/Replay Validation\n")
    h = R["risk"]
    for k in ("severity_matches_thresholds", "stored_risk_equals_event_risk", "risk_in_0_100", "trajectory_final_point_equals_event_risk", "trajectory_timestamps_monotone"):
        a(f"- {k}: {fmt(h[k])}")
    a(f"- Limited-baseline cap: {h['limited_baseline_cap']}; insufficient/no-baseline events with non-zero deviation: {h['insufficient_nonzero_deviation_violations']}; LOW-quality facility with facility risk: {h['low_quality_facility_with_risk_contribution_violations']}")
    a(f"- Thresholds {h['thresholds']}\n")
    a("## I. Live System Statistics\n")
    a("Operational statistics, **not accuracy**.\n")
    L2 = R["live"]
    for k, v in L2.items():
        if k != "note":
            a(f"- {k}: {v}")
    if R.get("shift"):
        a("\n**Distribution shift (live features vs RF training range):**")
        for k, v in R["shift"].items():
            a(f"- {k}: {fmt(v) if isinstance(v, dict) and 'numerator' in v else v}")
    a("\n## J. Scientific Claim Audit\n")
    ca = R["claims"]
    a(f"Scanned {ca['files_scanned']} files; {ca['hits_total']} pattern hits; {ca['hits_safe_denial']} are negations/denials (safe); **{len(ca['hits_review'])} need review**.\n")
    a("| file | line | pattern | current wording | recommended |\n|---|---|---|---|---|")
    for h in ca["hits_review"]:
        a(f"| {h['file']} | {h['line']} | {h['pattern']} | {h['text'].replace('|', '/')} | {h['recommended']} |")
    a("\n## K. Visual Validation\n")
    a(R["visual"])
    a("\n## L. Limitations\n")
    for x in R["limitations"]:
        a(f"- {x}")
    a("\n## M. Reproducibility\n")
    a("```\ncd <repo>\npython scripts/validate_accuracy.py            # full run (needs backend on :8000 and MAP_KEY for network sections)\npython scripts/validate_accuracy.py --skip-network --skip-refresh   # offline\n```")
    a("Seeds: corpus seed 7 (as implemented), RF random_state 42, ablation stability corpora seeds 100-119, bootstrap seed 0. Data: `backend/data/orbiflare.db` (read-only), `data/facilities/osm_gppd_facilities.parquet`, `data/reference/incidents/confirmed_incidents_india.csv`.")
    (REPORTS / "orbiflare_accuracy_validation.md").write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-network", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--skip-refresh", action="store_true")
    ap.add_argument("--visual", default="", help="text for section K (browser inspection outcome)")
    args = ap.parse_args()
    REPORTS.mkdir(exist_ok=True)
    rows = load_live_events()
    print("live events", len(rows), flush=True)
    rf, sent = rf_section(rows)
    X, _, _ = generate_synthetic_training_corpus()
    R = {"generated": NOW, "rf": rf, "sentinel": sent, "shift": shift_section(rows, X)}
    R["backtest"] = backtest_section(); print("backtest done", flush=True)
    R["facility"] = facility_section(rows); print("facility done", flush=True)
    R["firms_fidelity"] = {"skipped": "--skip-network"} if args.skip_network else firms_fidelity(); print("firms done", flush=True)
    R["tests"] = tests_section(args.skip_tests); print("tests done", flush=True)
    R["risk"] = risk_section()
    R["risk"]["trajectory_final_point_note"] = (
        "The stored event risk is computed by calculate_risk_stage() WITHOUT recent_frp (intensity uses the event's peak FRP); the trajectory's last point is computed WITH recent_frp = the latest observation's FRP. "
        "The two therefore differ slightly whenever the latest observation's FRP is not the peak. Every mismatch found has last-obs FRP != peak FRP; none has last == peak. Reported, NOT changed (evaluation-only pass).")
    R["live"] = live_section(rows, not args.skip_refresh); print("live done", flush=True)
    R["claims"] = claim_audit()
    R["visual"] = args.visual or "Not performed by the script; see the final response."
    ab = rf["ablations"]["without dist_nearest_facility_km"]
    nd = rf["ablations"]["without dist AND persistence (the two label-rule inputs)"]
    R["ablation_interpretation"] = (
        f"Removing facility distance alone changes macro-F1 by {ab['delta_macro_f1_vs_production']:+.3f}; removing both label-rule inputs (distance and persistence) changes it by {nd['delta_macro_f1_vs_production']:+.3f} "
        f"(macro-F1 {nd['macro_f1']:.3f}). Performance is carried by the same signals used to construct the proxy labels; the remaining features (BT, FRP, month, day/night) are generated from the same latent 'industrial world' flag, so they are correlated with the label for synthetic reasons, not because the physics was learned.")
    R["limitations"] = [
        "No verified ground truth: the RF has never been evaluated on a real, independently labelled industrial-incident set.",
        "The RF is trained on a synthetic corpus, not on real FIRMS observations; its 'geographic holdout' is a random row split.",
        "Proxy labels are built from facility proximity and persistence, which are also model features (circularity); metrics measure recovery of that rule.",
        "The 50 km sentinel is an unlearned-artefact risk for LOW-quality/no-context events (see E).",
        "Live events lie partly outside the training range (persistence, FRP); see the distribution-shift block in I.",
        "Historical incident backtest: 0/30 evaluable; the project has no archive acquisition path.",
        "Facility association is validated against the same dataset, so it validates the computation, not the completeness/accuracy of OSM/GPPD (most records are generic land-use, LOW quality).",
        "Baselines are limited by ~5 days of stored NRT history; most facilities are limited or insufficient.",
        "MAP_KEY rotation is still required externally.",
    ]
    (REPORTS / "orbiflare_accuracy_validation.json").write_text(json.dumps(R, indent=2, default=str), encoding="utf-8")
    write_md(R)
    print("written", REPORTS)


if __name__ == "__main__":
    main()
