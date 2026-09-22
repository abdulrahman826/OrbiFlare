from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AlertTransitionRequest(BaseModel):
    to_state: str
    actor: str = "operator"
    note: Optional[str] = None


class PipelineRunRequest(BaseModel):
    mode: str = "demo"


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
