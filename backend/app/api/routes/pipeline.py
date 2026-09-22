"""Admin/dev endpoint to (re)run the full pipeline -- what
scripts/rebuild_pipeline.py calls, exposed over HTTP for convenience (e.g. a
"Reset Demo Data" button)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import PipelineRunRequest
from app.intelligence.pipeline import run_full_pipeline
from app.storage.database import get_db

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/rebuild")
def rebuild(body: PipelineRunRequest, db: Session = Depends(get_db)) -> dict:
    return run_full_pipeline(db, mode=body.mode)
