# Demo Script (3-5 minutes)

Prerequisite: backend running on :8000 (auto-seeds the DEMO/SYNTHETIC scenario on first startup), frontend running on :3000.

## The scenario

**ORBIFLARE DEMO -- ESCALATING REFINERY THERMAL EVENT** (clearly labelled DEMO/SYNTHETIC throughout the UI):

- **Synthetic Refinery Alpha**: ~24 months of routine flaring history (FRP 20-40 MW, 1-2h, 2-4 observations, tight "Zone A" footprint, mostly 21:00-02:00 IST) -- then a current event that escalates to 118 MW peak, 5.5h duration, 11 observations, displaced ~1.7km into a new "Zone C", extending into daytime hours. This is the flagship walkthrough.
- **Synthetic Steel Plant Beta**: matches its own baseline closely -- demonstrates a LOW-risk, non-anomalous facility.
- **Synthetic Chemical Plant Gamma**: only one historical event ever recorded -- demonstrates the INSUFFICIENT baseline state honestly, with no fabricated deviation.
- An unassociated rural thermal signature with no nearby facility -- demonstrates the natural/agricultural-candidate path.

## Walkthrough

1. **Command Center** (`/command-center`) -- active events, KPIs (active/high-priority/escalating/persistent/needs-validation), map, priority feed. Point out the flagship event at the top.
2. Click into it -> **Investigation** (`/investigation/{id}`) -- header shows HIGH severity, ESCALATING trajectory, DEMO/SYNTHETIC badge.
3. **Map + Observation Timeline** -- the event's real location vs. the facility, and its FRP climbing across the observation history.
4. **Facility Thermal Twin table** -- NORMAL vs. CURRENT vs. DEVIATION for all 6 dimensions; point out that Recurrence is NOT flagged (this event isn't unusually frequent) while the other 5 are -- deviation isn't a rubber stamp, it's computed per-dimension.
5. **Why Flagged?** -- the Evidence Stack: supporting / contradicting / uncertain / unavailable, plus the correlation note between the FRP-driven intensity deviation and the ML signal.
6. **Alternative Explanations** -- "Abnormal industrial thermal event" as the primary hypothesis, with genuine alternatives and unknowns listed, not a single forced verdict.
7. **Risk Trajectory** -- the actual computed sequence (e.g. 29 -> 39 -> ... -> 74), labelled ESCALATING, with the exact required phrasing ("observed risk has increased consistently") -- never a future-fire prediction.
8. **Event Replay** (`/replay/{id}`) -- click Play Event and watch the real observation history unfold chronologically, with FRP/persistence/deviation/risk updating frame by frame.
9. **Thermal Twin page** (`/thermal-twins/{facility_id}`) -- the full historical behaviour profile (hour-of-day chart, distributions) for Alpha, then compare against Gamma's INSUFFICIENT baseline state.
10. Open the **Agent** (`/agent`) and ask: *"Why is this event high priority?"* (or click the suggested chip) -- the agent answers entirely from the real investigation data it just retrieved, with an "Open investigation" link back.
11. Back on the Investigation page, use **Operator Action** to move the event DETECTED -> VALIDATING -- an explicit, audited human action.
12. Close with **Limitations** (`/limitations`) and the **Model** page (`/model`) to show the system is upfront about proxy labels, baseline availability, satellite resolution, and everything else it does *not* claim.

## What to say if asked "what's different about this"

> "Most systems treat a satellite hotspot as the unit of analysis. OrbiFlare treats the evolving thermal event as the unit of analysis. It learns what normal thermal behaviour looks like for a facility, measures what's changed across intensity, persistence, duration, timing and space, and explains the resulting evidence and risk trajectory to the analyst -- who makes the final call."
