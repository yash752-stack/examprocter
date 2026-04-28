from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    student_name: Mapped[str] = mapped_column(String(128), nullable=False)
    exam_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="low", nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_face_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_motion_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_attention_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    last_alert: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    review_outcome: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    events: Mapped[list["IntegrityEvent"]] = relationship(
        "IntegrityEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="IntegrityEvent.created_at",
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
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ExamSession] = relationship("ExamSession", back_populates="events")
