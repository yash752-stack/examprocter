from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=128)
    exam_name: str = Field(..., min_length=2, max_length=128)


class EventIngest(BaseModel):
    event_type: str
    source: str = "browser"
    severity: str | None = None
    points: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class FrameIngest(BaseModel):
    image_base64: str


class ReviewUpdate(BaseModel):
    review_outcome: Literal["pending", "confirmed_flag", "false_positive", "clean"]


class IntegrityEventResponse(BaseModel):
    id: int
    session_id: str
    source: str
    event_type: str
    severity: str
    points: int
    risk_after_event: int
    details: dict[str, Any]
    created_at: datetime


class SessionResponse(BaseModel):
    id: str
    student_name: str
    exam_name: str
    status: str
    risk_score: int
    risk_level: str
    warning_count: int
    total_events: int
    latest_face_count: int
    latest_motion_score: float
    latest_attention_score: float
    last_alert: str
    review_outcome: str
    summary: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class EventBreakdownItem(BaseModel):
    event_type: str
    count: int


class DashboardOverview(BaseModel):
    total_sessions: int
    active_sessions: int
    flagged_sessions: int
    flagged_session_rate: float
    suspicious_events: int
    avg_risk_score: float
    false_positive_rate: float | None
    detection_accuracy: float | None
    event_breakdown: list[EventBreakdownItem]


class TimelineResponse(BaseModel):
    session_id: str
    events: list[IntegrityEventResponse]


class EventActionResponse(BaseModel):
    session: SessionResponse
    event: IntegrityEventResponse | None = None
    action: str
    alert: str
    analysis: dict[str, Any] | None = None
