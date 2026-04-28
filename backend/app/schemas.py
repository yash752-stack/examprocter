from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthLoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class ExamCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=128)
    description: str = Field(default="", max_length=1000)
    duration_minutes: int = Field(default=60, ge=15, le=300)
    warning_limit: int = Field(default=3, ge=1, le=10)
    fullscreen_required: bool = True
    allow_copy_paste: bool = False
    auto_terminate_on_limit: bool = False
    allowed_tabs: list[str] = Field(default_factory=list)
    access_code: str = Field(..., min_length=4, max_length=32)


class ExamResponse(BaseModel):
    id: str
    title: str
    description: str
    duration_minutes: int
    warning_limit: int
    fullscreen_required: bool
    allow_copy_paste: bool
    auto_terminate_on_limit: bool
    allowed_tabs: list[str]
    access_code: str
    created_by_name: str | None = None
    created_at: datetime


class ExamPublicResponse(BaseModel):
    id: str
    title: str
    description: str
    duration_minutes: int
    warning_limit: int
    fullscreen_required: bool
    allow_copy_paste: bool
    auto_terminate_on_limit: bool
    allowed_tabs: list[str]


class SessionCreate(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=128)
    student_email: str = Field(..., min_length=5, max_length=255)
    exam_id: str
    access_code: str = Field(..., min_length=4, max_length=32)


class EventIngest(BaseModel):
    event_type: str
    source: str = "browser"
    severity: str | None = None
    points: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    image_base64: str | None = None


class FrameIngest(BaseModel):
    image_base64: str


class ReviewUpdate(BaseModel):
    review_outcome: Literal["pending", "confirmed_flag", "false_positive", "clean"]
    notes: str = Field(default="", max_length=2000)


class IntegrityEventResponse(BaseModel):
    id: int
    session_id: str
    source: str
    event_type: str
    severity: str
    points: int
    risk_after_event: int
    is_evidence: bool
    details: dict[str, Any]
    created_at: datetime


class EvidenceSnapshotResponse(BaseModel):
    id: int
    session_id: str
    event_id: int | None
    event_type: str
    label: str
    note: str
    file_url: str
    metadata: dict[str, Any]
    created_at: datetime


class SessionResponse(BaseModel):
    id: str
    exam_id: str
    student_name: str
    student_email: str
    exam_name: str
    status: str
    risk_score: int
    risk_score_peak: int
    risk_level: str
    warning_count: int
    warning_stage: str
    total_events: int
    evidence_count: int
    latest_face_count: int
    latest_motion_score: float
    latest_attention_score: float
    current_action: str
    last_alert: str
    review_outcome: str
    review_notes: str
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None
    summary: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None
    exam_rules: ExamPublicResponse


class SessionStartResponse(SessionResponse):
    session_token: str


class EventBreakdownItem(BaseModel):
    event_type: str
    count: int


class DashboardOverview(BaseModel):
    total_sessions: int
    active_sessions: int
    review_pending: int
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


class EvidenceGalleryResponse(BaseModel):
    session_id: str
    items: list[EvidenceSnapshotResponse]


class RiskTrendPoint(BaseModel):
    created_at: datetime
    risk_score: int
    risk_level: str
    reason: str


class RiskTrendResponse(BaseModel):
    session_id: str
    points: list[RiskTrendPoint]


class EventActionResponse(BaseModel):
    session: SessionResponse
    event: IntegrityEventResponse | None = None
    action: str
    alert: str
    analysis: dict[str, Any] | None = None
