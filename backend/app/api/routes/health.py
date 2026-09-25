from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.firms_refresh import sensor_label, status_summary
from app.storage import models as m
from app.storage.database import get_db

router = APIRouter(tags=["health"])
settings = get_settings()


def verified_data_mode(db: Session) -> dict:
    """Data mode derived from what is actually STORED, not from configuration alone.

    LIVE_FIRMS only if non-demo FIRMS observations exist (i.e. a fetch succeeded and was stored); DEMO if only
    synthetic data exists; MIXED if both; otherwise EMPTY. A configured MAP_KEY alone never implies LIVE.
    """
    live_obs = db.scalar(select(func.count()).select_from(m.ObservationRecord).where(m.ObservationRecord.source == "FIRMS")) or 0
    demo_obs = db.scalar(select(func.count()).select_from(m.ObservationRecord).where(m.ObservationRecord.source == "DEMO")) or 0
    if live_obs and demo_obs:
        mode = "MIXED"
    elif live_obs:
        mode = "LIVE_FIRMS"
    elif demo_obs:
        mode = "DEMO"
    else:
        mode = "EMPTY"
    firms = status_summary(db)
    latest_live = db.scalar(select(func.max(m.ObservationRecord.timestamp)).where(m.ObservationRecord.source == "FIRMS"))
    firms["last_acquisition"] = latest_live.isoformat() + "Z" if latest_live else None   # from stored data, not the browser clock
    return {
        "data_mode": mode, "live_firms_observations": live_obs, "demo_observations": demo_obs,
        "firms_key_configured": firms["configured"], "firms": firms,
        "sensor_label": sensor_label(firms["satellites"], live=live_obs > 0, demo=demo_obs > 0),
    }


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok", "mode": settings.orbiflare_mode, "database": settings.database_url.split("://")[0],
            **verified_data_mode(db)}
