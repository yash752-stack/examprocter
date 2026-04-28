from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    auth_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    created_exams: Mapped[list["Exam"]] = relationship(
        "Exam",
        back_populates="created_by",
        foreign_keys="Exam.created_by_id",
    )
    reviewed_sessions: Mapped[list["ExamSession"]] = relationship(
        "ExamSession",
        back_populates="reviewed_by",
        foreign_keys="ExamSession.reviewed_by_id",
    )


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    warning_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    fullscreen_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_copy_paste: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_terminate_on_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_tabs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    access_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    created_by: Mapped[User | None] = relationship(
        "User",
        back_populates="created_exams",
        foreign_keys=[created_by_id],
    )
    sessions: Mapped[list["ExamSession"]] = relationship(
        "ExamSession",
        back_populates="exam",
    )


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True, nullable=False)
    student_name: Mapped[str] = mapped_column(String(128), nullable=False)
    student_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    exam_name: Mapped[str] = mapped_column(String(128), nullable=False)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_score_peak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="low", nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_stage: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_face_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_motion_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_attention_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    current_action: Mapped[str] = mapped_column(String(64), default="ignore", nullable=False)
    last_alert: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    review_outcome: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_risk_event_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_decay_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    exam: Mapped[Exam] = relationship("Exam", back_populates="sessions")
    reviewed_by: Mapped[User | None] = relationship(
        "User",
        back_populates="reviewed_sessions",
        foreign_keys=[reviewed_by_id],
    )
    events: Mapped[list["IntegrityEvent"]] = relationship(
        "IntegrityEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="IntegrityEvent.created_at",
    )
    snapshots: Mapped[list["RiskSnapshot"]] = relationship(
        "RiskSnapshot",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="RiskSnapshot.created_at",
    )


class IntegrityEvent(Base):
    __tablename__ = "integrity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("exam_sessions.id"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_after_event: Mapped[int] = mapped_column(Integer, nullable=False)
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ExamSession] = relationship("ExamSession", back_populates="events")


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("exam_sessions.id"), index=True, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ExamSession] = relationship("ExamSession", back_populates="snapshots")
