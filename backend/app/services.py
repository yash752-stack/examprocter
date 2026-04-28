from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ExamSession, IntegrityEvent
from .scoring import (
    apply_score,
    compute_risk_level,
    generate_summary,
    points_for_event,
    recommended_action,
    severity_for_event,
    warning_for_level,
)


def create_session(db: Session, student_name: str, exam_name: str) -> ExamSession:
    session = ExamSession(
        id=uuid4().hex[:12],
        student_name=student_name.strip(),
        exam_name=exam_name.strip(),
        status="active",
        summary="Monitoring started.",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def record_event(
    db: Session,
    session: ExamSession,
    event_type: str,
    source: str = "browser",
    details: dict | None = None,
    points_override: int | None = None,
    severity_override: str | None = None,
) -> IntegrityEvent:
    payload = details or {}
    points = points_override if points_override is not None else points_for_event(event_type, payload)
    severity = severity_override or severity_for_event(event_type, points)
    session.risk_score = apply_score(session.risk_score, points)
    session.risk_level = compute_risk_level(session.risk_score)
    session.last_activity_at = datetime.utcnow()
    session.total_events += 1

    action = recommended_action(session.risk_level)
    if action != "ignore":
        session.warning_count += 1
    session.last_alert = warning_for_level(session.risk_level)

    event = IntegrityEvent(
        session_id=session.id,
        source=source,
        event_type=event_type,
        severity=severity,
        points=points,
        risk_after_event=session.risk_score,
        details_json=json.dumps(payload),
    )
    db.add(event)
    db.flush()

    recent_events = db.execute(
        select(IntegrityEvent)
        .where(IntegrityEvent.session_id == session.id)
        .order_by(IntegrityEvent.created_at.desc())
        .limit(8)
    ).scalars().all()
    session.summary = generate_summary(
        risk_score=session.risk_score,
        risk_level=session.risk_level,
        events=list(reversed(recent_events)),
    )
    return event


def finalize_session(db: Session, session: ExamSession) -> ExamSession:
    session.status = "completed"
    session.ended_at = datetime.utcnow()
    session.last_activity_at = session.ended_at
    recent_events = db.execute(
        select(IntegrityEvent)
        .where(IntegrityEvent.session_id == session.id)
        .order_by(IntegrityEvent.created_at.desc())
        .limit(8)
    ).scalars().all()
    session.summary = generate_summary(
        risk_score=session.risk_score,
        risk_level=session.risk_level,
        events=list(reversed(recent_events)),
    )
    db.commit()
    db.refresh(session)
    return session


def build_overview(db: Session) -> dict:
    sessions = db.execute(select(ExamSession)).scalars().all()
    total_sessions = len(sessions)
    active_sessions = len([session for session in sessions if session.status == "active"])
    flagged_sessions = len([session for session in sessions if session.risk_score >= 40])
    flagged_session_rate = round((flagged_sessions / total_sessions) * 100, 1) if total_sessions else 0.0
    suspicious_events = db.scalar(select(func.count(IntegrityEvent.id))) or 0
    avg_risk_score = round(
        sum(session.risk_score for session in sessions) / total_sessions,
        1,
    ) if total_sessions else 0.0

    reviewed_sessions = [session for session in sessions if session.review_outcome != "pending"]
    reviewed_flagged = [
        session for session in sessions if session.review_outcome in {"confirmed_flag", "false_positive"}
    ]
    false_positives = len([session for session in sessions if session.review_outcome == "false_positive"])
    review_correct = len(
        [
            session
            for session in reviewed_sessions
            if session.review_outcome in {"confirmed_flag", "clean"}
        ]
    )

    false_positive_rate = (
        round((false_positives / len(reviewed_flagged)) * 100, 1) if reviewed_flagged else None
    )
    detection_accuracy = (
        round((review_correct / len(reviewed_sessions)) * 100, 1) if reviewed_sessions else None
    )

    breakdown_counter = Counter(
        db.execute(select(IntegrityEvent.event_type)).scalars().all()
    )
    event_breakdown = [
        {"event_type": event_type, "count": count}
        for event_type, count in breakdown_counter.most_common(6)
    ]

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "flagged_sessions": flagged_sessions,
        "flagged_session_rate": flagged_session_rate,
        "suspicious_events": suspicious_events,
        "avg_risk_score": avg_risk_score,
        "false_positive_rate": false_positive_rate,
        "detection_accuracy": detection_accuracy,
        "event_breakdown": event_breakdown,
    }


def seed_demo_data(db: Session) -> dict:
    existing_sessions = db.scalar(select(func.count(ExamSession.id))) or 0
    if existing_sessions:
        return {
            "created_sessions": 0,
            "message": "Existing sessions detected. Demo seed skipped to avoid duplicate noise.",
        }

    scenarios = [
        {
            "student_name": "Aarav Singh",
            "exam_name": "Quant Aptitude Mock",
            "review_outcome": "clean",
            "events": [
                ("copy", "browser", {"selection": "question 2"}),
            ],
        },
        {
            "student_name": "Ira Menon",
            "exam_name": "Data Analyst Screening",
            "review_outcome": "false_positive",
            "events": [
                ("tab_switch", "browser", {"hidden_seconds": 2}),
                ("looking_away", "detector", {"attention_score": 0.39}),
            ],
        },
        {
            "student_name": "Kabir Sharma",
            "exam_name": "Campus Hiring Assessment",
            "review_outcome": "confirmed_flag",
            "events": [
                ("multiple_faces", "detector", {"face_count": 2}),
                ("tab_switch", "browser", {"hidden_seconds": 6}),
                ("phone_detected", "manual", {"note": "demo trigger"}),
            ],
        },
    ]

    for index, scenario in enumerate(scenarios):
        session = create_session(
            db,
            student_name=scenario["student_name"],
            exam_name=scenario["exam_name"],
        )
        session.started_at = datetime.utcnow() - timedelta(minutes=(index + 1) * 14)
        session.last_activity_at = session.started_at
        session.review_outcome = scenario["review_outcome"]

        for event_type, source, details in scenario["events"]:
            event = record_event(
                db,
                session=session,
                event_type=event_type,
                source=source,
                details=details,
            )
            event.created_at = session.started_at + timedelta(minutes=session.total_events * 2)

        if scenario["review_outcome"] == "clean":
            session.risk_score = max(session.risk_score - 8, 0)
            session.risk_level = compute_risk_level(session.risk_score)
        session.summary = generate_summary(session.risk_score, session.risk_level, session.events)

    db.commit()
    return {
        "created_sessions": len(scenarios),
        "message": "Demo sessions created successfully.",
    }
