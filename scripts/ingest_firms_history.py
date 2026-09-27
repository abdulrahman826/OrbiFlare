"""Admin operation: fetch the historical FIRMS window for India (resumable, cached) and build the Thermal Twin baseline files.

    python scripts/ingest_firms_history.py                 # fetch missing chunks + build
    python scripts/ingest_firms_history.py --build-only    # rebuild from the cached rows (no network)
    FIRMS_HISTORY_DAYS=365 python scripts/ingest_firms_history.py

Never run by the dashboard or the live refresh. The MAP_KEY comes from the server environment and is never printed.
"""
from __future__ import annotations

import argparse
import json

import os
from pathlib import Path

import _pathsetup  # noqa: F401

os.chdir(Path(__file__).resolve().parent.parent / "backend")   # settings (.env) resolve exactly as in the running app

from app.ingestion import firms_history as fh
from app.intelligence import history_baseline as hb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--days", type=int, default=None)
    args = ap.parse_args()
    if not args.build_only:
        m = fh.ingest_history(days=args.days, progress=lambda i, n, c, rows: print(f"  chunk {i}/{n} {c.product} {c.start} +{c.days}d -> {rows} rows", flush=True))
        print("fetch:", json.dumps({k: m.get(k) for k in ("status", "window_first", "window_last", "requested_days", "covered_days", "covered_days_by_satellite", "chunks_planned", "chunks_downloaded", "chunks_cached")}))
        if m.get("chunks_failed"):
            print("  failed chunks:", m["chunks_failed"])
        if m.get("status") in ("NOT_CONFIGURED", "FAILED"):
            print("  ", m.get("message"))
    b = hb.build_history_baseline()
    print("baseline:", json.dumps({k: b.get(k) for k in ("status", "historical_observations", "observations_near_facilities", "historical_events_total", "historical_events_with_facility", "facilities_with_history")}))


if __name__ == "__main__":
    main()
