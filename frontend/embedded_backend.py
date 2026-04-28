from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.app.database import Base, SessionLocal, engine
from backend.app.evidence import EVIDENCE_DIR
from backend.app.models import EvidenceSnapshot, Exam, ExamSession, IntegrityEvent, RiskSnapshot, User
from backend.app.services import (
    authenticate_user,
    bootstrap_platform,
    build_overview,
    create_exam,
    list_evidence_for_session,
    list_exams,
    list_sessions,
    review_session,
    seed_demo_data,
    serialize_allowed_tabs,
)

ADMIN_ROLES = {"admin", "invigilator"}


def initialize_demo_data() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        bootstrap_platform(db)
        seed_demo_data(db)


def resolve_asset_path(file_url: str) -> str:
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url
    if file_url.startswith("/evidence/"):
        return str(EVIDENCE_DIR / Path(file_url).name)
    return file_url


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    current_user: dict[str, Any] | None = None,
    auth_required: bool = True,
) -> dict[str, Any] | list[dict[str, Any]]:
    initialize_demo_data()
    payload = payload or {}
    params = params or {}

    with SessionLocal() as db:
        if path == "/api/v1/auth/login" and method.upper() == "POST":
            user = authenticate_user(db, payload.get("email", ""), payload.get("password", ""))
            if not user:
                raise PermissionError("Invalid email or password.")
            return {
                "access_token": user.auth_token or f"embedded:{user.id}",
                "user": _user_response(user),
            }

        user = _require_user(current_user, auth_required)

        if path == "/api/v1/dashboard/overview" and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            return build_overview(db)

        if path == "/api/v1/dashboard/exams" and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            return [_exam_response(exam) for exam in list_exams(db)]

        if path == "/api/v1/dashboard/exams" and method.upper() == "POST":
            _require_roles(user, {"admin"})
            reviewer = db.get(User, user["id"])
            if reviewer is None:
                raise LookupError("Current user not found.")
            exam = create_exam(
                db,
                title=str(payload.get("title", "")),
                description=str(payload.get("description", "")),
                duration_minutes=int(payload.get("duration_minutes", 60)),
                warning_limit=int(payload.get("warning_limit", 3)),
                fullscreen_required=bool(payload.get("fullscreen_required", True)),
                allow_copy_paste=bool(payload.get("allow_copy_paste", False)),
                auto_terminate_on_limit=bool(payload.get("auto_terminate_on_limit", False)),
                allowed_tabs=[str(item) for item in payload.get("allowed_tabs", [])],
                access_code=str(payload.get("access_code", "")),
                created_by=reviewer,
            )
            return _exam_response(exam)

        if path == "/api/v1/dashboard/sessions" and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            return [
                _session_response(session)
                for session in list_sessions(
                    db,
                    exam_id=params.get("exam_id"),
                    risk_levels=_normalize_list(params.get("risk_level")),
                    statuses=_normalize_list(params.get("status")),
                    review_outcomes=_normalize_list(params.get("review_outcome")),
                    only_flagged=bool(params.get("only_flagged", False)),
                )
            ]

        if path.startswith("/api/v1/dashboard/sessions/") and path.endswith("/timeline") and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            session_id = path.split("/")[5]
            session = _get_session_or_404(db, session_id)
            events = db.execute(
                select(IntegrityEvent)
                .where(IntegrityEvent.session_id == session.id)
                .order_by(IntegrityEvent.created_at.desc())
            ).scalars().all()
            return {
                "session_id": session.id,
                "events": [_event_response(event) for event in events],
            }

        if path.startswith("/api/v1/dashboard/sessions/") and path.endswith("/evidence") and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            session_id = path.split("/")[5]
            session = _get_session_or_404(db, session_id)
            items = list_evidence_for_session(db, session.id)
            return {
                "session_id": session.id,
                "items": [_evidence_response(item) for item in items],
            }

        if path.startswith("/api/v1/dashboard/sessions/") and path.endswith("/risk-trend") and method.upper() == "GET":
            _require_roles(user, ADMIN_ROLES)
            session_id = path.split("/")[5]
            session = _get_session_or_404(db, session_id)
            points = db.execute(
                select(RiskSnapshot)
                .where(RiskSnapshot.session_id == session.id)
                .order_by(RiskSnapshot.created_at.asc())
            ).scalars().all()
            return {
                "session_id": session.id,
                "points": [
                    {
                        "created_at": _dt(point.created_at),
                        "risk_score": point.risk_score,
                        "risk_level": point.risk_level,
                        "reason": point.reason,
                    }
                    for point in points
                ],
            }

        if path.startswith("/api/v1/dashboard/sessions/") and path.endswith("/review") and method.upper() == "PATCH":
            _require_roles(user, ADMIN_ROLES)
            session_id = path.split("/")[5]
            session = _get_session_or_404(db, session_id)
            reviewer = db.get(User, user["id"])
            if reviewer is None:
                raise LookupError("Current user not found.")
            updated = review_session(
                db,
                session,
                review_outcome=str(payload.get("review_outcome", "pending")),
                notes=str(payload.get("notes", "")),
                reviewer=reviewer,
            )
            return _session_response(updated)

        if path == "/api/v1/demo/seed" and method.upper() == "POST":
            _require_roles(user, {"admin"})
            return seed_demo_data(db)

    raise NotImplementedError(f"Embedded mode does not implement {method.upper()} {path}.")


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if value == "":
        return []
    return [str(value)]


def _require_user(current_user: dict[str, Any] | None, auth_required: bool) -> dict[str, Any]:
    if not auth_required:
        return current_user or {}
    if not current_user:
        raise PermissionError("Sign in to continue.")
    return current_user


def _require_roles(current_user: dict[str, Any], allowed_roles: set[str]) -> None:
    if current_user.get("role") not in allowed_roles:
        raise PermissionError("You do not have access to this resource.")


def _get_session_or_404(db, session_id: str) -> ExamSession:
    session = db.get(ExamSession, session_id)
    if session is None:
        raise LookupError("Session not found.")
    return session


def _dt(value) -> str | None:
    return value.isoformat() if value is not None else None


def _user_response(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
    }


def _exam_public_response(exam: Exam) -> dict[str, Any]:
    return {
        "id": exam.id,
        "title": exam.title,
        "description": exam.description,
        "duration_minutes": exam.duration_minutes,
        "warning_limit": exam.warning_limit,
        "fullscreen_required": exam.fullscreen_required,
        "allow_copy_paste": exam.allow_copy_paste,
        "auto_terminate_on_limit": exam.auto_terminate_on_limit,
        "allowed_tabs": serialize_allowed_tabs(exam),
    }


def _exam_response(exam: Exam) -> dict[str, Any]:
    return {
        "id": exam.id,
        "title": exam.title,
        "description": exam.description,
        "duration_minutes": exam.duration_minutes,
        "warning_limit": exam.warning_limit,
        "fullscreen_required": exam.fullscreen_required,
        "allow_copy_paste": exam.allow_copy_paste,
        "auto_terminate_on_limit": exam.auto_terminate_on_limit,
        "allowed_tabs": serialize_allowed_tabs(exam),
        "access_code": exam.access_code,
        "created_by_name": exam.created_by.full_name if exam.created_by else None,
        "created_at": _dt(exam.created_at),
    }


def _event_response(event: IntegrityEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "session_id": event.session_id,
        "source": event.source,
        "event_type": event.event_type,
        "severity": event.severity,
        "points": event.points,
        "risk_after_event": event.risk_after_event,
        "is_evidence": event.is_evidence,
        "details": json.loads(event.details_json),
        "created_at": _dt(event.created_at),
    }


def _evidence_response(item: EvidenceSnapshot) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "event_id": item.event_id,
        "event_type": item.event_type,
        "label": item.label,
        "note": item.note,
        "file_url": item.file_url,
        "metadata": json.loads(item.metadata_json),
        "created_at": _dt(item.created_at),
    }


def _session_response(session: ExamSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "exam_id": session.exam_id,
        "student_name": session.student_name,
        "student_email": session.student_email,
        "exam_name": session.exam_name,
        "status": session.status,
        "risk_score": session.risk_score,
        "risk_score_peak": session.risk_score_peak,
        "risk_level": session.risk_level,
        "warning_count": session.warning_count,
        "warning_stage": session.warning_stage,
        "total_events": session.total_events,
        "evidence_count": session.evidence_count,
        "latest_face_count": session.latest_face_count,
        "latest_motion_score": session.latest_motion_score,
        "latest_attention_score": session.latest_attention_score,
        "current_action": session.current_action,
        "last_alert": session.last_alert,
        "review_outcome": session.review_outcome,
        "review_notes": session.review_notes,
        "reviewed_by_name": session.reviewed_by.full_name if session.reviewed_by else None,
        "reviewed_at": _dt(session.reviewed_at),
        "summary": session.summary,
        "started_at": _dt(session.started_at),
        "last_activity_at": _dt(session.last_activity_at),
        "ended_at": _dt(session.ended_at),
        "exam_rules": _exam_public_response(session.exam),
    }
