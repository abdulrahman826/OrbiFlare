"""Read-only status of the historical FIRMS baseline (the ingestion itself is an admin script, never triggered from here)."""
from __future__ import annotations

from fastapi import APIRouter

from app.intelligence import history_baseline as hb

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/status")
def history_status() -> dict:
    return hb.get_store().status()
