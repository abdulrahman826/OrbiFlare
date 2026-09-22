from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AgentQuery(BaseModel):
    message: str


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any]
    result_summary: str


class ResultCard(BaseModel):
    type: str  # "event" | "facility" | "comparison" | "report"
    title: str
    subtitle: Optional[str] = None
    data: dict[str, Any]


class UIAction(BaseModel):
    action: str  # "open_investigation" | "open_facility" | "none"
    target_id: Optional[str] = None


class AgentResponse(BaseModel):
    text: str
    tool_calls: list[ToolCall] = []
    result_cards: list[ResultCard] = []
    ui_action: Optional[UIAction] = None
