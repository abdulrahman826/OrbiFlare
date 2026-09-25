"""On-demand NASA FIRMS refresh. The MAP_KEY stays on the server; only summaries/short errors reach the client."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.ingestion import firms_refresh
from app.storage.database import get_db

router = APIRouter(prefix="/firms", tags=["firms"])


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    try:
        return firms_refresh.refresh_firms(db)
    except firms_refresh.FirmsError as err:
        return JSONResponse(status_code=err.http_status, content={
            "status": "FAILED", "code": err.code, "message": err.message, "showing": "last available data",
        })


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    return firms_refresh.status_summary(db)
