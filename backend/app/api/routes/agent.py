from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.runtime import run_query
from app.agent.schemas import AgentQuery, AgentResponse
from app.storage.database import get_db

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentResponse)
def agent_query(body: AgentQuery, db: Session = Depends(get_db)) -> AgentResponse:
    return run_query(db, body.message)
