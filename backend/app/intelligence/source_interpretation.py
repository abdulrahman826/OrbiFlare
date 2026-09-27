"""Source interpretation -- a DESCRIPTIVE evidence-fusion layer, separate from the ML classes and from the risk score.

It answers "what kind of thermal source is the available evidence most consistent with?" using conservative CANDIDATE labels:

    INDUSTRIAL_SOURCE_CANDIDATE             evidence associated with an industrial facility / persistent industrial behaviour
    AGRICULTURAL_VEGETATION_CANDIDATE       evidence more consistent with agricultural / vegetation burning
    PERSISTENT_THERMAL_SOURCE_CANDIDATE     repeated thermal activity, but attribution is ambiguous
    NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE  context more consistent with a non-industrial, non-agricultural source (low strength)
    UNCERTAIN                               insufficient or conflicting evidence

Hard rules (all covered by tests):
  * No class is a confirmed fire and none is a probability. Strength is HIGH / MODERATE / LOW / UNCERTAIN.
  * No single signal decides: an industrial candidate needs at least two distinct supporting signals.
  * Absence of a facility is NOT evidence of an agricultural or natural source.
  * A missing signal is listed as unavailable, never guessed.
  * ML evidence is facility-informed, so it counts at half weight (no double counting of facility proximity / persistence).
  * This layer adds NO risk points and never changes the ML classes, the risk engine or event state.

FIRMS `type` field: 0 = presumed vegetation fire, 1 = active volcano, 2 = other static land source, 3 = offshore. NASA provides it only for
Standard Processing rows (historical); NRT rows carry no type, so it is used only through the historical record at the same facility.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.context.facilities import THERMAL_KEYWORDS
from app.model.train import AGRI_MONTHS

INDUSTRIAL = "INDUSTRIAL_SOURCE_CANDIDATE"
AGRICULTURAL = "AGRICULTURAL_VEGETATION_CANDIDATE"
PERSISTENT = "PERSISTENT_THERMAL_SOURCE_CANDIDATE"
NATURAL = "NATURAL_OTHER_THERMAL_SOURCE_CANDIDATE"
UNCERTAIN = "UNCERTAIN"
CLASSES = [INDUSTRIAL, AGRICULTURAL, PERSISTENT, NATURAL, UNCERTAIN]
LABELS = {
    INDUSTRIAL: "Industrial-source candidate", AGRICULTURAL: "Agricultural / vegetation-fire candidate",
    PERSISTENT: "Persistent thermal-source candidate", NATURAL: "Natural / other thermal-source candidate", UNCERTAIN: "Uncertain",
}
MEANINGS = {
    INDUSTRIAL: "Evidence is associated with an industrial facility or persistent industrial thermal behaviour. This is not a confirmed industrial fire.",
    AGRICULTURAL: "Evidence is more consistent with agricultural or vegetation burning. This is not a confirmed agricultural fire.",
    PERSISTENT: "Repeated thermal activity is present, but the evidence does not attribute it specifically to an industrial or agricultural source.",
    NATURAL: "Available context is more consistent with a non-industrial, non-agricultural thermal source. Evidence is limited.",
    UNCERTAIN: "Evidence is insufficient or conflicting, so no source interpretation is asserted.",
}
ALTERNATIVES = {
    INDUSTRIAL: ["planned thermal process activity (flare, kiln, furnace)", "a mixed 375 m pixel containing more than one thermal source", "a nearby unrelated thermal source"],
    AGRICULTURAL: ["a small industrial or domestic thermal source", "a mixed 375 m pixel", "burning unrelated to crops"],
    PERSISTENT: ["an industrial process not represented in the facility data", "recurrent burning at the same spot", "a mixed 375 m pixel"],
    NATURAL: ["an unmapped industrial or domestic source (facility data may be incomplete)", "agricultural burning outside the usual season"],
    UNCERTAIN: ["any of the interpretations above; more observations, a facility baseline or imagery would help"],
}
PERSISTENT_OBS = 6
PERSISTENT_HOURS = 6.0
TRANSIENT_OBS = 2
TRANSIENT_HOURS = 3.0
MIN_TYPED_HISTORY = 5


@dataclass
class Signal:
    name: str
    supports: str          # one of CLASSES, or "CONTRA_INDUSTRIAL"
    weight: float
    text: str


@dataclass
class Interpretation:
    classification: str
    strength: str
    scores: dict[str, float]
    supporting: list[dict] = field(default_factory=list)
    contradicting: list[dict] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {"classification": self.classification, "label": LABELS[self.classification], "strength": self.strength}

    def full(self) -> dict:
        return {**self.summary(), "meaning": MEANINGS[self.classification], "scores": self.scores, "supporting_evidence": self.supporting,
                "contradicting_evidence": self.contradicting, "unavailable_evidence": self.unavailable, "alternative_explanations": ALTERNATIVES[self.classification],
                "disclaimer": "Source interpretation is evidence-based and not a confirmed fire classification.",
                "facility_note": "Facility association is spatial context, not source attribution."}


def _heat_relevant(facility_type: str | None) -> bool:
    t = (facility_type or "").lower().replace("_", " ")
    return any(k in t for k in THERMAL_KEYWORDS)


def _step_down(strength: str) -> str:
    return {"HIGH": "MODERATE", "MODERATE": "LOW"}.get(strength, strength)


def interpret(event, *, facility_type: str | None = None, history_events: int = 0, typed_history: int = 0, static_history: int = 0) -> Interpretation:
    """`event` is a ThermalEvent (its stored facility association, ML class and counts). All other inputs are optional context."""
    obs, dur = int(event.observation_count or 0), float(event.duration_hours or 0.0)
    q = event.facility_context_quality
    has_facility = event.facility_id is not None and event.facility_distance_km is not None
    usable = has_facility and q in ("HIGH", "MEDIUM", None)          # None: legacy/unclassified record keeps the previous behaviour
    persistent = obs >= PERSISTENT_OBS or dur >= PERSISTENT_HOURS
    transient = obs <= TRANSIENT_OBS and dur < TRANSIENT_HOURS
    agri_season = event.first_detected.month in AGRI_MONTHS
    ml = getattr(event, "classification", None)
    ml_name = getattr(ml, "value", ml)
    ml_a = ml_name == "PERSISTENT_INDUSTRIAL_THERMAL_SOURCE"
    ml_b = ml_name == "NATURAL_AGRICULTURAL_FIRE_CANDIDATE"

    sig: list[Signal] = []
    contra: list[dict] = []
    unavailable: list[str] = []
    nonheat_site = False

    # ---- facility context (spatial association only)
    if not has_facility:
        unavailable.append("facility context: no eligible facility within the search radius (absence is not evidence of a natural or agricultural source)")
    elif q == "LOW":
        contra.append({"signal": "facility_context", "text": "only a generic land-use record is nearby (low-quality context); not counted as industrial evidence"})
    elif usable and _heat_relevant(facility_type):
        w = 2.0 if q == "HIGH" else 1.0
        sig.append(Signal("facility_context", INDUSTRIAL, w, f"{event.facility_distance_km:.2f} km from an eligible {(facility_type or 'facility').replace('_', ' ')} facility ({(q or 'unclassified').lower()}-quality context; spatial association only)"))
    elif usable:
        nonheat_site = True
        contra.append({"signal": "facility_context", "text": f"nearby facility type ({(facility_type or 'unknown').replace('_', ' ')}) is not clearly heat-producing"})

    # ---- behaviour
    if persistent:
        text = f"persistent activity: {obs} observations over {dur:.1f} h"
        sig.append(Signal("persistence", INDUSTRIAL if usable else PERSISTENT, 1.0, text))
    elif transient:
        sig.append(Signal("transient", AGRICULTURAL, 0.5, f"short-lived detection ({obs} observation(s), {dur:.1f} h), typical of transient burning"))
    if has_facility and usable and history_events >= 2:
        w = 1.5 if history_events >= 4 else 0.75
        sig.append(Signal("recurrence", INDUSTRIAL, w, f"{history_events} earlier thermal events associated with the same facility (recurring at the location)"))
    elif has_facility and usable:
        unavailable.append("recurrence: too little history at this facility")

    # ---- season / agriculture
    if agri_season:
        sig.append(Signal("agri_season", AGRICULTURAL, 1.0, f"detected in a typical crop-residue burning month ({event.first_detected:%B})"))
    unavailable.append("land-use / vegetation cover: no agricultural land-use dataset is configured")

    # ---- FIRMS type (historical record at this facility only)
    if typed_history >= MIN_TYPED_HISTORY:
        frac = static_history / typed_history
        if frac >= 0.5:
            sig.append(Signal("firms_type", INDUSTRIAL, 1.5, f"NASA FIRMS marks {static_history} of {typed_history} historical detections at this facility as 'other static land source'"))
        elif frac <= 0.1:
            sig.append(Signal("firms_type", AGRICULTURAL, 1.5, f"NASA FIRMS marks {typed_history - static_history} of {typed_history} historical detections here as presumed vegetation fire or other non-static source"))
    else:
        unavailable.append("FIRMS type: not provided for near-real-time rows and too little typed history at this location")

    # ---- ML evidence (facility-informed => half weight; never independent confirmation)
    if ml_a:
        sig.append(Signal("ml_evidence", INDUSTRIAL, 0.5, "ML evidence: Class A (industrial-source development class); correlated with facility proximity and persistence, so it counts at half weight"))
    elif ml_b:
        sig.append(Signal("ml_evidence", AGRICULTURAL, 0.5, "ML evidence: Class B (natural/agricultural development class); correlated with facility distance, so it counts at half weight"))
    else:
        unavailable.append("ML evidence: no class assigned (no usable facility context)")

    score = {c: 0.0 for c in (INDUSTRIAL, AGRICULTURAL, PERSISTENT)}
    kinds = {c: set() for c in score}
    for s in sig:
        if s.supports in score:
            score[s.supports] += s.weight
            kinds[s.supports].add(s.name)
    # An industrial candidate can never rest on a single signal; an agricultural one can never rest on the mere absence of a facility.
    ind_ok = score[INDUSTRIAL] >= 2.0 and len(kinds[INDUSTRIAL]) >= 2
    agr_ok = score[AGRICULTURAL] >= 1.5 and len(kinds[AGRICULTURAL]) >= 2 and not usable
    ind_present = score[INDUSTRIAL] >= 1.5
    agr_present = score[AGRICULTURAL] >= 1.5

    # Positive evidence only: a short-lived detection whose nearest identified site is NOT a heat-producing installation. A missing facility,
    # or a merely transient detection, is never enough (absence of context is not evidence of a natural source).
    natural_ok = nonheat_site and transient and not agri_season and not (ind_present or agr_present)
    if ind_ok and score[AGRICULTURAL] < 1.0:
        cls = INDUSTRIAL
        strength = "HIGH" if score[INDUSTRIAL] >= 4.0 else "MODERATE" if score[INDUSTRIAL] >= 3.0 else "LOW"
        if score[AGRICULTURAL] > 0:
            strength = _step_down(strength)
    elif agr_ok and score[INDUSTRIAL] < 1.0:
        cls = AGRICULTURAL
        strength = "MODERATE" if score[AGRICULTURAL] >= 2.5 else "LOW"
    elif ind_present and agr_present:
        cls, strength = UNCERTAIN, "UNCERTAIN"                       # conflicting evidence
        contra.append({"signal": "conflict", "text": "industrial-type and agricultural-type evidence are both present"})
    elif persistent:
        cls = PERSISTENT
        strength = "MODERATE" if obs >= 10 and dur >= PERSISTENT_HOURS else "LOW"
    elif natural_ok:
        cls, strength = NATURAL, "LOW"
    else:
        cls, strength = UNCERTAIN, "UNCERTAIN"

    def pack(sigs):
        return [{"signal": s.name, "supports": s.supports, "weight": s.weight, "text": s.text} for s in sigs]
    supporting = [x for x in pack(sig) if (cls == UNCERTAIN) or x["supports"] == cls or (cls == INDUSTRIAL and x["supports"] == INDUSTRIAL)]
    dedup, seen = [], set()
    for x in supporting:
        if (x["signal"], x["supports"]) not in seen:
            seen.add((x["signal"], x["supports"]))
            dedup.append(x)
    others = [x for x in pack(sig) if x not in supporting and x["supports"] != cls]
    contra += [{"signal": x["signal"], "text": f"favours {LABELS.get(x['supports'], x['supports']).lower()}: {x['text']}"} for x in others]
    return Interpretation(cls, strength, {LABELS[k]: round(v, 2) for k, v in score.items()}, dedup, contra, unavailable)
