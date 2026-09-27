"""AUDIT ONLY -- READ-ONLY forensic analysis of the 'Uncertain' source-interpretation population. NOT part of the application.

Reads the stored database (opened with mode=ro) and the precomputed history files, calls the PRODUCTION `source_interpretation.interpret()` unchanged
(a pure function) on every stored event, and reconstructs -- from the stored fields and the production code's own gates -- why each event stayed
Uncertain. It writes nothing to the database, changes no application file and patches nothing. Outputs go to the directory given as argv[1].

    python scripts/audit_uncertain_events.py <output_dir>
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import _pathsetup  # noqa: F401
import os

os.chdir(Path(__file__).resolve().parent.parent / "backend")
from app.context.facilities import THERMAL_KEYWORDS  # noqa: E402
from app.intelligence import history_baseline as hb  # noqa: E402
from app.intelligence import source_interpretation as si  # noqa: E402
from app.model.schemas import MLClass, ThermalEvent  # noqa: E402
from app.model.train import AGRI_MONTHS  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OUT.mkdir(parents=True, exist_ok=True)
DB = Path(__file__).resolve().parent.parent / "backend" / "data" / "orbiflare.db"
con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

fac = {r["facility_id"]: dict(r) for r in con.execute("select facility_id,name,facility_type,source from facilities")}
twin = {}
for r in con.execute("select facility_id,baseline_confidence,payload from thermal_twins"):
    import json as _j
    p = _j.loads(r["payload"])
    twin[r["facility_id"]] = {"state": r["baseline_confidence"], "n": p.get("historical_event_count", 0), "frp": (p.get("normal_frp") or {}).get("median"), "pers": (p.get("normal_persistence") or {}).get("median")}
dev = {}
for r in con.execute("select event_id,overall_deviation_score,payload from deviations"):
    p = json.loads(r["payload"])
    dev[r["event_id"]] = {"overall": r["overall_deviation_score"], "state": p.get("baseline_confidence"), **{d: bool((p.get(d) or {}).get("is_notable") or (p.get(d) or {}).get("is_significant")) for d in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence")}}
risk = {}
for r in con.execute("select event_id,risk_score,severity,payload from risk_assessments"):
    p = json.loads(r["payload"])
    risk[r["event_id"]] = {"score": r["risk_score"], "sev": r["severity"], "baseline": p.get("baseline_status"), "dev_contrib": p.get("deviation_contribution"), "factors": {f["name"]: f["contribution"] for f in p.get("risk_factors", [])}}
obs = defaultdict(lambda: {"frp": [], "bt": [], "conf": Counter(), "sat": Counter(), "dn": Counter()})
for r in con.execute("select event_id,frp,brightness_temperature,confidence,satellite,day_night from observations where event_id is not null"):
    o = obs[r["event_id"]]
    if r["frp"] is not None: o["frp"].append(r["frp"])
    if r["brightness_temperature"] is not None: o["bt"].append(r["brightness_temperature"])
    o["conf"][r["confidence"]] += 1; o["sat"][r["satellite"]] += 1; o["dn"][r["day_night"]] += 1

store = hb.get_store()
rows = []
for r in con.execute("select * from events where is_demo=0"):
    e = ThermalEvent(
        event_id=r["event_id"], first_detected=datetime.fromisoformat(r["first_detected"]), last_detected=datetime.fromisoformat(r["last_detected"]), duration_hours=r["duration_hours"],
        observation_count=r["observation_count"], peak_frp=r["peak_frp"], mean_frp=r["mean_frp"], peak_bt=r["peak_bt"], mean_bt=r["mean_bt"], centroid_lat=r["centroid_lat"], centroid_lon=r["centroid_lon"],
        facility_id=r["facility_id"], facility_distance_km=r["facility_distance_km"], facility_context_quality=r["facility_context_quality"], status=r["status"],
        classification=MLClass(r["classification"]) if r["classification"] else None, ml_p_industrial=r["ml_p_industrial"], ml_p_natural=r["ml_p_natural"],
        risk_score=r["risk_score"], trajectory_direction=r["trajectory_direction"], source_observation_ids=[])
    f = fac.get(e.facility_id) if e.facility_id else None
    tw = twin.get(e.facility_id) if e.facility_id else None
    typed, static = store.type_counts(e.facility_id) if e.facility_id else (0, 0)
    res = si.interpret(e, facility_type=f["facility_type"] if f else None, history_events=tw["n"] if tw else 0, typed_history=typed, static_history=static)
    q = e.facility_context_quality
    has_fac = e.facility_id is not None and e.facility_distance_km is not None
    usable = has_fac and q in ("HIGH", "MEDIUM", None)
    ftype = (f["facility_type"] if f else "") or ""
    heat = any(k in ftype.lower().replace("_", " ") for k in THERMAL_KEYWORDS)
    d = dev.get(e.event_id, {})
    ob = obs.get(e.event_id)
    row = {
        "event_id": e.event_id, "status": e.status.value if hasattr(e.status, "value") else e.status, "severity": r["severity"], "risk": r["risk_score"],
        "obs": e.observation_count, "duration_h": e.duration_hours, "first": r["first_detected"], "month": e.first_detected.month, "in_agri_season": e.first_detected.month in AGRI_MONTHS,
        "frp_peak": e.peak_frp, "frp_mean": e.mean_frp, "bt_peak": e.peak_bt, "conf": dict(ob["conf"]) if ob else None, "sat": dict(ob["sat"]) if ob else None, "dn": dict(ob["dn"]) if ob else None,
        "traj": r["trajectory_direction"], "dev": d.get("overall"), "dev_notable_dims": [k for k in ("intensity", "persistence", "duration", "temporal", "spatial", "recurrence") if d.get(k)],
        "facility": e.facility_id, "fac_name": f["name"] if f else None, "fac_type": ftype or None, "fac_source": f["source"] if f else None, "fac_dist": e.facility_distance_km, "fac_quality": q,
        "usable": usable, "heat_type": heat, "twin_state": tw["state"] if tw else "NONE", "twin_history": tw["n"] if tw else 0, "twin_frp": tw["frp"] if tw else None,
        "ml_class": e.classification.value if e.classification else None, "ml_p_ind": r["ml_p_industrial"], "ml_low_conf": bool(r["ml_anomaly_low_confidence"]),
        "risk_baseline": risk.get(e.event_id, {}).get("baseline"), "risk_dev_contrib": risk.get(e.event_id, {}).get("dev_contrib"),
        "typed_history": typed, "static_history": static,
        "interp": res.classification, "strength": res.strength, "scores": res.scores, "supporting": [(x["signal"], x["supports"]) for x in res.supporting],
        "contradicting": [x["signal"] for x in res.contradicting], "unavailable": res.unavailable,
    }
    rows.append(row)

N = len(rows)
unc = [x for x in rows if x["interp"] == si.UNCERTAIN]
intr = [x for x in rows if x["interp"] != si.UNCERTAIN]
pct = lambda a, b: f"{100.0 * a / b:.1f}%" if b else "n/a"

# ---------------------------------------------------------------- production thresholds (read from the code, not invented)
T = {"persistent_obs": si.PERSISTENT_OBS, "persistent_hours": si.PERSISTENT_HOURS, "transient_obs": si.TRANSIENT_OBS, "transient_hours": si.TRANSIENT_HOURS, "min_typed_history": si.MIN_TYPED_HISTORY,
     "agri_months": sorted(AGRI_MONTHS)}

def persistent(x): return x["obs"] >= si.PERSISTENT_OBS or (x["duration_h"] or 0) >= si.PERSISTENT_HOURS
def transient(x): return x["obs"] <= si.TRANSIENT_OBS and (x["duration_h"] or 0) < si.TRANSIENT_HOURS
def meaningful_dev(x): return x["twin_state"] in ("ESTABLISHED", "LIMITED") and (x["dev"] or 0) >= 50
def actionable(x):  # mirror of frontend/src/lib/mapFocus.ts isActionable (display predicate)
    if x["interp"] != si.UNCERTAIN: return True
    if x["severity"] in ("HIGH", "CRITICAL", "MEDIUM"): return True
    if x["obs"] >= 4: return True
    return meaningful_dev(x)

# ---------------------------------------------------------------- PRIMARY root cause (one per uncertain event), following the production gate order
IND, AGR = si.LABELS[si.INDUSTRIAL], si.LABELS[si.AGRICULTURAL]
def ind_kinds(x): return {n for n, sup in x["supporting"] if sup == si.INDUSTRIAL}
def ind_ok(x): return x["scores"][IND] >= 2.0 and len(ind_kinds(x)) >= 2

def primary(x):
    if "conflict" in x["contradicting"]: return "Conflicting evidence (industrial-type and agricultural-type both >= 1.5)"
    if x["usable"] and x["heat_type"]:
        if ind_ok(x) and x["scores"][AGR] >= 1.0:
            return "Industrial evidence threshold MET (facility + recurrence >= 2.0) but BLOCKED: agricultural-type counter-evidence >= 1.0 (short-lived detection 0.5 + ML Class B 0.5)"
        return "Usable heat-relevant facility, but industrial score < 2.0 or fewer than 2 distinct industrial signals (not persistent, little/no recurrence history)"
    if x["usable"]:
        return "Nearby identified facility is not heat-producing; no positive non-industrial evidence (natural/other rule not met)"
    if x["facility"] is not None and x["fac_quality"] == "LOW":
        return "Only a generic land-use facility record (LOW quality) is nearby; not counted, and the event is not persistent"
    return "No facility context within the search radius, and the event is not persistent (no attribution signal available)"

# ---------------------------------------------------------------- CONTRIBUTING conditions (multi-label; each is a production gate that was not satisfied)
def contributing(x):
    c = []
    if not persistent(x): c.append("Not persistent (< 6 observations and < 6 h)")
    if x["obs"] == 1: c.append("Single observation")
    if x["facility"] is None: c.append("No facility context")
    elif x["fac_quality"] == "LOW": c.append("Facility context is LOW quality (generic land use)")
    elif not x["heat_type"]: c.append("Facility type not heat-relevant")
    if x["usable"] and x["heat_type"] and x["twin_history"] < 2: c.append("Recurrence not established (< 2 earlier events at the facility)")
    if x["twin_state"] == "NONE": c.append("No Thermal Twin (no facility)")
    elif x["twin_state"] == "INSUFFICIENT": c.append("Thermal Twin INSUFFICIENT")
    elif x["twin_state"] == "LIMITED": c.append("Thermal Twin LIMITED")
    if x["ml_class"] is None: c.append("ML class not assigned (no usable facility context)")
    elif x["ml_class"] == "NATURAL_AGRICULTURAL_FIRE_CANDIDATE": c.append("ML evidence is Class B (only counts toward agricultural, half weight)")
    elif x["ml_class"] == "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE": c.append("ML evidence Class A (half weight, cannot decide alone)")
    if transient(x): c.append("Short-lived detection (<=2 obs, <3 h): adds an agricultural-type signal (0.5), never an industrial one")
    if x["usable"] and x["heat_type"] and ind_ok(x) and x["scores"][AGR] >= 1.0: c.append("Industrial threshold met but suppressed by agricultural-type counter-evidence (>= 1.0)")
    if not x["in_agri_season"]: c.append("Outside crop-burning months (agricultural season signal absent)")
    if x["typed_history"] < si.MIN_TYPED_HISTORY: c.append("No usable FIRMS type history at this location")
    if (x["dev"] or 0) < 50 or x["twin_state"] not in ("ESTABLISHED", "LIMITED"): c.append("No meaningful behavioural deviation (or no baseline to deviate from)")
    return c

for x in unc:
    x["primary"] = primary(x)
    x["contrib"] = contributing(x)

R = {"thresholds": T, "totals": {"events": N, "uncertain": len(unc), "interpreted": len(intr), "interp_counts": Counter(x["interp"] for x in rows), "actionable": sum(actionable(x) for x in rows)}}
prim = Counter(x["primary"] for x in unc)
R["primary"] = [(k, v, pct(v, len(unc)), pct(v, N)) for k, v in prim.most_common()]
cc = Counter(c for x in unc for c in x["contrib"])
R["contributing"] = [(k, v, pct(v, len(unc)), pct(v, N)) for k, v in cc.most_common()]

# facility analysis
def fstate(x):
    if x["facility"] is None: return "no facility"
    return {"HIGH": "HIGH quality", "MEDIUM": "MEDIUM quality", "LOW": "LOW quality"}.get(x["fac_quality"], "unclassified")
R["facility_state_uncertain"] = Counter(fstate(x) for x in unc)
R["facility_state_interpreted"] = Counter(fstate(x) for x in intr)
uf = [x for x in unc if x["facility"] is not None]
uu = [x for x in unc if x["usable"]]
R["uncertain_with_facility_any"] = len(uf)
R["uncertain_with_usable_facility"] = len(uu)
R["uncertain_with_facility_detail"] = {
    "facility proximity (any facility in radius)": len(uf), "usable (HIGH/MEDIUM) facility": len(uu), "usable + heat-relevant type": sum(1 for x in uu if x["heat_type"]),
    "facility + persistent": sum(1 for x in uf if persistent(x)), "facility + Thermal Twin history (>=1 event)": sum(1 for x in uf if x["twin_history"] >= 1),
    "facility + established/limited twin": sum(1 for x in uf if x["twin_state"] in ("ESTABLISHED", "LIMITED")), "facility + meaningful deviation (>=50, E/L baseline)": sum(1 for x in uf if meaningful_dev(x)),
    "facility + ML class assigned": sum(1 for x in uf if x["ml_class"]), "usable + ML class assigned": sum(1 for x in uu if x["ml_class"]),
}

# twin cross-tab
tw_states = ["ESTABLISHED", "LIMITED", "INSUFFICIENT", "NONE"]
R["twin_x_interp"] = {"Uncertain": {s: sum(1 for x in unc if x["twin_state"] == s) for s in tw_states}, "Interpreted": {s: sum(1 for x in intr if x["twin_state"] == s) for s in tw_states}}
for name in (si.INDUSTRIAL, si.PERSISTENT, si.AGRICULTURAL, si.NATURAL):
    R["twin_x_interp"][name] = {s: sum(1 for x in rows if x["interp"] == name and x["twin_state"] == s) for s in tw_states}

# behaviour
def dist(vals):
    v = sorted(vals)
    if not v: return {}
    q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1)))]
    return {"n": len(v), "min": v[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p95": q(0.95), "max": v[-1]}
R["behaviour"] = {
    "obs": dist([x["obs"] for x in unc]), "duration_h": dist([x["duration_h"] or 0 for x in unc]), "risk": dist([x["risk"] or 0 for x in unc]), "deviation_where_computed": dist([x["dev"] for x in unc if x["twin_state"] in ("ESTABLISHED", "LIMITED") and x["dev"] is not None]),
    "obs_hist": dict(sorted(Counter(x["obs"] for x in unc).items())[:12]), "trajectory": Counter(x["traj"] for x in unc), "severity": Counter(x["severity"] for x in unc),
    "counts": {">=4 obs": sum(x["obs"] >= 4 for x in unc), ">=6 obs (production persistence threshold)": sum(x["obs"] >= 6 for x in unc), ">=10 obs": sum(x["obs"] >= 10 for x in unc),
               "duration >= 6 h (production persistence threshold)": sum((x["duration_h"] or 0) >= 6 for x in unc), "persistent by production rule (obs>=6 or dur>=6h)": sum(persistent(x) for x in unc),
               "deviation >= 50": sum((x["dev"] or 0) >= 50 for x in unc), "established baseline + deviation >= 50": sum(x["twin_state"] == "ESTABLISHED" and (x["dev"] or 0) >= 50 for x in unc),
               "meaningful deviation (E/L baseline, >=50)": sum(meaningful_dev(x) for x in unc), "ESCALATING trajectory": sum(x["traj"] == "ESCALATING" for x in unc),
               "MEDIUM risk": sum(x["severity"] == "MEDIUM" for x in unc), "HIGH/CRITICAL risk": sum(x["severity"] in ("HIGH", "CRITICAL") for x in unc),
               "recurrence at facility (>=2 earlier events)": sum(x["twin_history"] >= 2 for x in unc)},
}

# matrix
def dims(x):
    return {"facility": x["usable"], "persistence": persistent(x), "deviation": meaningful_dev(x), "ml": x["ml_class"] is not None, "baseline": x["twin_state"] in ("ESTABLISHED", "LIMITED")}
def yes(rs, k): return sum(1 for x in rs if dims(x)[k])
R["matrix"] = {}
for name, rs in (("Uncertain", unc), (si.INDUSTRIAL, [x for x in rows if x["interp"] == si.INDUSTRIAL]), (si.PERSISTENT, [x for x in rows if x["interp"] == si.PERSISTENT])):
    R["matrix"][name] = {"n": len(rs), **{k: f"{yes(rs, k)} ({pct(yes(rs, k), len(rs))})" for k in ("facility", "persistence", "baseline", "deviation", "ml")}}
def combo(rs, keys): return sum(1 for x in rs if all(dims(x)[k] for k in keys))
R["combos_uncertain"] = {
    "facility + persistence": combo(unc, ["facility", "persistence"]), "facility + deviation": combo(unc, ["facility", "deviation"]), "persistence + deviation": combo(unc, ["persistence", "deviation"]),
    "facility + persistence + deviation": combo(unc, ["facility", "persistence", "deviation"]), "facility + persistence + ML": combo(unc, ["facility", "persistence", "ml"]),
    "facility + persistence + established twin": sum(1 for x in unc if x["usable"] and persistent(x) and x["twin_state"] == "ESTABLISHED"),
    "3+ of (usable facility, persistence, meaningful deviation, ML class, E/L baseline)": sum(1 for x in unc if sum(dims(x).values()) >= 3),
    "4+ of the same five": sum(1 for x in unc if sum(dims(x).values()) >= 4),
}

# agricultural / natural
R["agri"] = {
    "events first detected in a crop-burning month (Apr/May/Oct/Nov)": sum(x["in_agri_season"] for x in rows), "month distribution of first_detected": Counter(x["month"] for x in rows),
    "transient (<=2 obs and <3 h)": sum(transient(x) for x in rows), "transient + no usable facility": sum(1 for x in rows if transient(x) and not x["usable"]),
    "events with ANY agricultural score > 0": sum(1 for x in rows if x["scores"].get(si.LABELS[si.AGRICULTURAL], 0) > 0), "agricultural score >= 1.5": sum(1 for x in rows if x["scores"].get(si.LABELS[si.AGRICULTURAL], 0) >= 1.5),
    "events with an agricultural-supporting FIRMS type signal": sum(1 for x in rows if ("firms_type", si.AGRICULTURAL) in x["supporting"]),
    "events with ML Class B": sum(1 for x in rows if x["ml_class"] == "NATURAL_AGRICULTURAL_FIRE_CANDIDATE"),
    "ML Class B + transient + no usable facility (would still need the season signal)": sum(1 for x in rows if x["ml_class"] == "NATURAL_AGRICULTURAL_FIRE_CANDIDATE" and transient(x) and not x["usable"]),
    "land-use dataset available": False,
}
R["natural"] = {
    "events with a usable NON-heat facility nearby (required positive evidence)": sum(1 for x in rows if x["usable"] and not x["heat_type"]),
    "... and transient": sum(1 for x in rows if x["usable"] and not x["heat_type"] and transient(x)), "... and transient and outside crop months": sum(1 for x in rows if x["usable"] and not x["heat_type"] and transient(x) and not x["in_agri_season"]),
    "usable non-heat facility, any persistence": [(x["event_id"], x["fac_type"], x["obs"], x["duration_h"]) for x in rows if x["usable"] and not x["heat_type"]][:10],
    "facility types of usable non-heat facilities": Counter(x["fac_type"] for x in rows if x["usable"] and not x["heat_type"]).most_common(10),
}

# actionable
act = [x for x in rows if actionable(x)]
au = [x for x in act if x["interp"] == si.UNCERTAIN]
def why(x):
    r = []
    if x["severity"] in ("HIGH", "CRITICAL", "MEDIUM"): r.append(f"{x['severity']} risk")
    if x["obs"] >= 4: r.append(">=4 observations")
    if meaningful_dev(x): r.append("meaningful deviation")
    return "+".join(r) or "interpreted"
R["actionable"] = {"total": len(act), "interpreted": sum(1 for x in act if x["interp"] != si.UNCERTAIN), "uncertain_and_actionable": len(au), "interpreted_total": len(intr),
                   "interpreted_not_actionable": sum(1 for x in intr if not actionable(x)),
                   "uncertain_reasons": Counter(why(x) for x in au), "uncertain_actionable_risk": dist([x["risk"] or 0 for x in au]), "uncertain_actionable_obs": dist([x["obs"] for x in au]),
                   "uncertain_actionable_dev": dist([x["dev"] for x in au if x["dev"] is not None]), "uncertain_actionable_facility": Counter(fstate(x) for x in au), "uncertain_actionable_twin": Counter(x["twin_state"] for x in au),
                   "uncertain_actionable_severity": Counter(x["severity"] for x in au)}

# strong-but-uncertain / genuinely low-evidence (existing fields + existing thresholds only)
def strong_dims(x):
    d = {"usable facility": x["usable"], "persistent (obs>=6 or >=6 h)": persistent(x), "meaningful deviation (E/L baseline, >=50)": meaningful_dev(x), "ML class assigned": x["ml_class"] is not None,
         "established Thermal Twin": x["twin_state"] == "ESTABLISHED", "ESCALATING trajectory": x["traj"] == "ESCALATING", "MEDIUM/HIGH risk": x["severity"] in ("MEDIUM", "HIGH", "CRITICAL"),
         ">=4 observations": x["obs"] >= 4}
    return d
for x in unc:
    x["strong_dims"] = [k for k, v in strong_dims(x).items() if v]
sbu = [x for x in unc if len(x["strong_dims"]) >= 3]
sbu4 = [x for x in unc if len(x["strong_dims"]) >= 4]
R["strong_but_uncertain"] = {"definition": "uncertain AND >=3 of: usable facility, persistent (production threshold), meaningful deviation (E/L baseline, >=50), ML class assigned, established twin, ESCALATING, MEDIUM+ risk, >=4 observations",
    "count_ge3": len(sbu), "pct_of_uncertain": pct(len(sbu), len(unc)), "count_ge4": len(sbu4), "profiles": Counter(tuple(x["strong_dims"]) for x in sbu).most_common(8),
    "examples": [{"id": x["event_id"], "risk": x["risk"], "sev": x["severity"], "obs": x["obs"], "dur": x["duration_h"], "dev": x["dev"], "twin": x["twin_state"], "fac": f"{x['fac_name']} ({x['fac_type']}, {x['fac_quality']})", "ml": x["ml_class"], "traj": x["traj"], "why_uncertain": x["primary"]} for x in sorted(sbu, key=lambda z: -len(z["strong_dims"]) * 1000 - (z["risk"] or 0))[:8]]}
lowe = {"few obs (<=2)": lambda x: x["obs"] <= 2, "single obs": lambda x: x["obs"] == 1, "no facility": lambda x: x["facility"] is None, "no usable facility": lambda x: not x["usable"],
        "no usable baseline (none/insufficient)": lambda x: x["twin_state"] in ("NONE", "INSUFFICIENT"), "no ML class": lambda x: x["ml_class"] is None, "deviation < 50 or none": lambda x: not meaningful_dev(x),
        "LOW risk": lambda x: x["severity"] == "LOW", "not persistent": lambda x: not persistent(x), "duration < 1 h": lambda x: (x["duration_h"] or 0) < 1}
R["genuinely_low"] = {"each": {k: (sum(1 for x in unc if f(x)), pct(sum(1 for x in unc if f(x)), len(unc))) for k, f in lowe.items()}}
strict = [x for x in unc if x["obs"] <= 2 and not x["usable"] and x["twin_state"] in ("NONE", "INSUFFICIENT") and not meaningful_dev(x) and x["severity"] == "LOW" and not persistent(x)]
R["genuinely_low"]["strict (obs<=2, no usable facility, no usable baseline, no meaningful deviation, LOW risk, not persistent)"] = (len(strict), pct(len(strict), len(unc)))
broad = [x for x in unc if x["severity"] == "LOW" and not persistent(x) and not meaningful_dev(x) and x["obs"] < 4]
R["genuinely_low"]["broad (LOW risk, not persistent, no meaningful deviation, <4 obs)"] = (len(broad), pct(len(broad), len(unc)))
both = {x["event_id"] for x in sbu} & {x["event_id"] for x in broad}
R["genuinely_low"]["overlap_with_strong_but_uncertain"] = len(both)
rest = [x for x in unc if x["event_id"] not in {y["event_id"] for y in sbu} and x["event_id"] not in {y["event_id"] for y in broad}]
R["middle_band_uncertain"] = len(rest)

# reproducibility check against the DB-independent live API is done by the caller; here we self-report the class counts
(OUT / "audit_summary.json").write_text(json.dumps(R, indent=1, default=str), encoding="utf-8")
with open(OUT / "uncertain_events.csv", "w", newline="", encoding="utf-8") as fh:
    keys = ["event_id", "status", "severity", "risk", "obs", "duration_h", "first", "frp_peak", "traj", "dev", "facility", "fac_name", "fac_type", "fac_quality", "fac_dist", "usable", "heat_type", "twin_state", "twin_history", "ml_class", "ml_p_ind", "in_agri_season", "interp", "strength", "primary"]
    w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for x in unc: w.writerow(x)
json.dump(rows, open(OUT / "all_events_audit_dataset.json", "w", encoding="utf-8"), default=str)
print(json.dumps({"interp_counts": R["totals"]["interp_counts"], "N": N, "uncertain": len(unc), "actionable": R["totals"]["actionable"]}, default=str))
