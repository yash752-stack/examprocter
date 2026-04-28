from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import hash_password, issue_auth_token, issue_session_token, verify_password
from .models import Exam, ExamSession, IntegrityEvent, RiskSnapshot, User
from .scoring import compute_risk_level, generate_summary, points_for_event, severity_for_event

RISK_DECAY_POINTS = 5
RISK_DECAY_WINDOW_MINUTES = 5
TERMINATION_SCORE = 120


def serialize_allowed_tabs(exam: Exam) -> list[str]:
    try:
        payload = json.loads(exam.allowed_tabs_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in payload]


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
) -> User:
    user = User(
        full_name=full_name,
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.execute(
        select(User).where(User.email == email.lower().strip())
    ).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.auth_token = issue_auth_token()
    db.commit()
    db.refresh(user)
    return user


def get_user_by_token(db: Session, token: str) -> User | None:
    return db.execute(
        select(User).where(User.auth_token == token, User.is_active.is_(True))
    ).scalar_one_or_none()


def create_exam(
    db: Session,
    *,
    title: str,
    description: str,
    duration_minutes: int,
    warning_limit: int,
    fullscreen_required: bool,
    allow_copy_paste: bool,
    auto_terminate_on_limit: bool,
    allowed_tabs: list[str],
    access_code: str,
    created_by: User | None = None,
) -> Exam:
    normalized_code = access_code.strip().upper()
    existing = db.execute(
        select(Exam).where(Exam.access_code == normalized_code)
    ).scalar_one_or_none()
    if existing:
        raise ValueError("That access code is already in use.")

    exam = Exam(
        id=uuid4().hex[:12],
        title=title.strip(),
        description=description.strip(),
        duration_minutes=duration_minutes,
        warning_limit=warning_limit,
        fullscreen_required=fullscreen_required,
        allow_copy_paste=allow_copy_paste,
        auto_terminate_on_limit=auto_terminate_on_limit,
        allowed_tabs_json=json.dumps([tab.strip() for tab in allowed_tabs if tab.strip()]),
        access_code=normalized_code,
        created_by=created_by,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


def bootstrap_platform(db: Session) -> None:
    if not db.scalar(select(func.count(User.id))):
        admin = create_user(
            db,
            full_name="Aanya Rao",
            email="admin@examprocter.dev",
            password="Admin@123",
            role="admin",
        )
        create_user(
            db,
            full_name="Rishi Mehta",
            email="invigilator@examprocter.dev",
            password="Invigilator@123",
            role="invigilator",
        )
        create_user(
            db,
            full_name="Demo Student",
            email="student@examprocter.dev",
            password="Student@123",
            role="student",
        )
        db.commit()
        db.refresh(admin)

    if not db.scalar(select(func.count(Exam.id))):
        admin = db.execute(
            select(User).where(User.role == "admin").order_by(User.id.asc())
        ).scalar_one()
        create_exam(
            db,
            title="Campus Hiring Assessment",
            description="General aptitude and integrity-monitored screening exam.",
            duration_minutes=45,
            warning_limit=3,
            fullscreen_required=True,
            allow_copy_paste=False,
            auto_terminate_on_limit=False,
            allowed_tabs=["Exam Portal", "Calculator"],
            access_code="CAMPUS2026",
            created_by=admin,
        )
        create_exam(
            db,
            title="Data Analyst Screening",
            description="Timed analytics test with strong copy-paste restrictions.",
            duration_minutes=60,
            warning_limit=3,
            fullscreen_required=True,
            allow_copy_paste=False,
            auto_terminate_on_limit=True,
            allowed_tabs=["Exam Portal", "SQL Sandbox"],
            access_code="ANALYST2026",
            created_by=admin,
        )


def _record_snapshot(
    db: Session,
    session: ExamSession,
    *,
    reason: str,
    created_at: datetime,
) -> None:
    db.add(
        RiskSnapshot(
            session_id=session.id,
            risk_score=session.risk_score,
            risk_level=session.risk_level,
            reason=reason,
            created_at=created_at,
        )
    )


def _recent_events(db: Session, session_id: str, limit: int = 8) -> list[IntegrityEvent]:
    return list(
        reversed(
            db.execute(
                select(IntegrityEvent)
                .where(IntegrityEvent.session_id == session_id)
                .order_by(IntegrityEvent.created_at.desc())
                .limit(limit)
            ).scalars().all()
        )
    )


def _refresh_summary(db: Session, session: ExamSession) -> None:
    session.summary = generate_summary(
        risk_score=session.risk_score,
        risk_level=session.risk_level,
        events=_recent_events(db, session.id),
    )


def _apply_action_rules(session: ExamSession, *, points: int) -> tuple[str, str]:
    if session.status == "terminated":
        return "terminate_session", "Exam already terminated."

    warning_limit = session.exam.warning_limit
    previous_stage = session.warning_stage
    action = "ignore"
    alert = "Monitoring continues quietly."

    if (
        points >= 70
        or session.risk_score >= TERMINATION_SCORE
        or session.warning_count >= warning_limit
        or (previous_stage == "strict" and session.risk_score >= 80)
    ):
        session.warning_count = max(session.warning_count, warning_limit)
        session.warning_stage = "final"
        if session.exam.auto_terminate_on_limit:
            session.status = "terminated"
            action = "terminate_session"
            alert = "Exam terminated after repeated or severe integrity violations."
        else:
            session.status = "flagged"
            action = "flag_for_review"
            alert = "Critical risk detected. Session flagged for urgent admin review."
    elif session.risk_score >= 80:
        session.warning_count = max(session.warning_count, 2)
        session.warning_stage = "strict"
        session.status = "flagged"
        if previous_stage != "strict":
            action = "strict_warning"
            alert = "Strict warning issued. Continued violations may end the exam."
        else:
            action = "flag_for_review"
            alert = "High-risk pattern detected. Session flagged for review."
    elif session.risk_score >= 40:
        if session.warning_count < 1:
            session.warning_count = 1
            session.warning_stage = "soft"
            action = "soft_warning"
            alert = "Soft warning issued. Please remain focused on the exam."
        else:
            action = "warn"
            alert = "Medium-risk pattern detected. Monitoring continues."
    else:
        action = "ignore"
        alert = "Monitoring continues quietly."

    session.current_action = action
    session.last_alert = alert
    return action, alert


def apply_risk_decay(
    db: Session,
    session: ExamSession,
    *,
    reference_time: datetime | None = None,
    snapshot_reason: str = "clean_behavior",
) -> int:
    if session.status in {"completed", "terminated"} or session.risk_score <= 0:
        return 0

    now = reference_time or datetime.utcnow()
    decay_anchor = max(session.last_risk_event_at, session.last_decay_at)
    elapsed_seconds = (now - decay_anchor).total_seconds()
    window_seconds = RISK_DECAY_WINDOW_MINUTES * 60
    decay_steps = int(elapsed_seconds // window_seconds)
    if decay_steps <= 0:
        return 0

    decay_points = min(session.risk_score, decay_steps * RISK_DECAY_POINTS)
    session.risk_score = max(0, session.risk_score - decay_points)
    session.risk_level = compute_risk_level(session.risk_score)
    session.last_decay_at = decay_anchor + timedelta(seconds=decay_steps * window_seconds)
    session.current_action = "risk_decay"
    session.last_alert = (
        f"Risk cooled by {decay_points} points after {decay_steps * RISK_DECAY_WINDOW_MINUTES} clean minutes."
    )
    _record_snapshot(db, session, reason=snapshot_reason, created_at=now)
    _refresh_summary(db, session)
    return decay_points


def create_session(
    db: Session,
    *,
    student_name: str,
    student_email: str,
    exam_id: str,
    access_code: str,
) -> ExamSession:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise LookupError("Exam not found.")
    if exam.access_code != access_code.strip().upper():
        raise PermissionError("Invalid exam access code.")

    now = datetime.utcnow()
    session = ExamSession(
        id=uuid4().hex[:12],
        exam=exam,
        student_name=student_name.strip(),
        student_email=student_email.lower().strip(),
        exam_name=exam.title,
        session_token=issue_session_token(),
        status="active",
        risk_score=0,
        risk_score_peak=0,
        risk_level="low",
        warning_count=0,
        warning_stage="none",
        current_action="ignore",
        summary="Monitoring started.",
        started_at=now,
        last_activity_at=now,
        last_risk_event_at=now,
        last_decay_at=now,
    )
    db.add(session)
    _record_snapshot(db, session, reason="session_started", created_at=now)
    db.commit()
    db.refresh(session)
    return session


def touch_session_activity(
    db: Session,
    session: ExamSession,
    *,
    reference_time: datetime | None = None,
    reason: str = "clean_frame",
) -> int:
    now = reference_time or datetime.utcnow()
    session.last_activity_at = now
    return apply_risk_decay(db, session, reference_time=now, snapshot_reason=reason)


def record_event(
    db: Session,
    session: ExamSession,
    *,
    event_type: str,
    source: str = "browser",
    details: dict | None = None,
    points_override: int | None = None,
    severity_override: str | None = None,
    recorded_at: datetime | None = None,
) -> IntegrityEvent:
    if session.status in {"completed", "terminated"}:
        raise ValueError("This session is no longer accepting events.")

    payload = details or {}
    now = recorded_at or datetime.utcnow()
    apply_risk_decay(db, session, reference_time=now, snapshot_reason="pre_event_decay")

    points = points_override if points_override is not None else points_for_event(event_type, payload)
    severity = severity_override or severity_for_event(event_type, points)
    is_evidence = severity == "high" or points >= 50

    session.risk_score = max(0, session.risk_score + points)
    session.risk_score_peak = max(session.risk_score_peak, session.risk_score)
    session.risk_level = compute_risk_level(session.risk_score)
    session.last_activity_at = now
    session.last_risk_event_at = now
    session.total_events += 1
    if is_evidence:
        session.evidence_count += 1

    event = IntegrityEvent(
        session_id=session.id,
        source=source,
        event_type=event_type,
        severity=severity,
        points=points,
        risk_after_event=session.risk_score,
        is_evidence=is_evidence,
        details_json=json.dumps(payload),
        created_at=now,
    )
    db.add(event)
    db.flush()

    _apply_action_rules(session, points=points)
    _record_snapshot(db, session, reason=f"event:{event_type}", created_at=now)
    _refresh_summary(db, session)
    return event


def finalize_session(db: Session, session: ExamSession) -> ExamSession:
    now = datetime.utcnow()
    touch_session_activity(db, session, reference_time=now, reason="pre_end_decay")
    session.status = "completed" if session.status != "terminated" else session.status
    session.ended_at = now
    session.last_activity_at = now
    session.current_action = "session_ended"
    _record_snapshot(db, session, reason="session_ended", created_at=now)
    _refresh_summary(db, session)
    db.commit()
    db.refresh(session)
    return session


def review_session(
    db: Session,
    session: ExamSession,
    *,
    review_outcome: str,
    notes: str,
    reviewer: User,
) -> ExamSession:
    session.review_outcome = review_outcome
    session.review_notes = notes.strip()
    session.reviewed_by = reviewer
    session.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def list_exams(db: Session) -> list[Exam]:
    return db.execute(select(Exam).order_by(Exam.created_at.desc())).scalars().all()


def list_sessions(
    db: Session,
    *,
    exam_id: str | None = None,
    risk_levels: list[str] | None = None,
    statuses: list[str] | None = None,
    review_outcomes: list[str] | None = None,
    only_flagged: bool = False,
) -> list[ExamSession]:
    sessions = db.execute(
        select(ExamSession).order_by(ExamSession.risk_score.desc(), ExamSession.last_activity_at.desc())
    ).scalars().all()

    touched = False
    for session in sessions:
        touched = bool(
            touch_session_activity(
                db,
                session,
                reference_time=datetime.utcnow(),
                reason="dashboard_refresh",
            )
        ) or touched
    if touched:
        db.commit()

    normalized_levels = {level.lower() for level in (risk_levels or []) if level}
    normalized_statuses = {status.lower() for status in (statuses or []) if status}
    normalized_reviews = {review.lower() for review in (review_outcomes or []) if review}

    filtered: list[ExamSession] = []
    for session in sessions:
        if exam_id and session.exam_id != exam_id:
            continue
        if normalized_levels and session.risk_level.lower() not in normalized_levels:
            continue
        if normalized_statuses and session.status.lower() not in normalized_statuses:
            continue
        if normalized_reviews and session.review_outcome.lower() not in normalized_reviews:
            continue
        if only_flagged and session.risk_score < 40 and session.status not in {"flagged", "terminated"}:
            continue
        filtered.append(session)
    return filtered


def build_overview(db: Session) -> dict:
    sessions = list_sessions(db)
    total_sessions = len(sessions)
    active_sessions = len([session for session in sessions if session.status == "active"])
    review_pending = len([session for session in sessions if session.review_outcome == "pending"])
    flagged_sessions = len(
        [
            session
            for session in sessions
            if session.risk_score >= 40 or session.status in {"flagged", "terminated"}
        ]
    )
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
        for event_type, count in breakdown_counter.most_common(8)
    ]

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "review_pending": review_pending,
        "flagged_sessions": flagged_sessions,
        "flagged_session_rate": flagged_session_rate,
        "suspicious_events": suspicious_events,
        "avg_risk_score": avg_risk_score,
        "false_positive_rate": false_positive_rate,
        "detection_accuracy": detection_accuracy,
        "event_breakdown": event_breakdown,
    }


def seed_demo_data(db: Session) -> dict:
    bootstrap_platform(db)
    existing_sessions = db.scalar(select(func.count(ExamSession.id))) or 0
    if existing_sessions:
        return {
            "created_sessions": 0,
            "message": "Existing sessions detected. Demo seed skipped to avoid duplicate noise.",
        }

    admin = db.execute(select(User).where(User.role == "admin")).scalar_one()
    exams = {
        exam.title: exam
        for exam in db.execute(select(Exam)).scalars().all()
    }

    scenarios = [
        {
            "student_name": "Aarav Singh",
            "student_email": "aarav@example.com",
            "exam": exams["Campus Hiring Assessment"],
            "review_outcome": "clean",
            "review_notes": "Minor copy event but no persistent suspicious pattern.",
            "events": [
                ("copy", "browser", {"selection": "question 2"}, 2),
            ],
        },
        {
            "student_name": "Ira Menon",
            "student_email": "ira@example.com",
            "exam": exams["Data Analyst Screening"],
            "review_outcome": "false_positive",
            "review_notes": "Candidate briefly looked away and changed focus once.",
            "events": [
                ("tab_switch", "browser", {"hidden_seconds": 2}, 2),
                ("looking_away", "detector", {"attention_score": 0.39}, 4),
            ],
        },
        {
            "student_name": "Kabir Sharma",
            "student_email": "kabir@example.com",
            "exam": exams["Campus Hiring Assessment"],
            "review_outcome": "confirmed_flag",
            "review_notes": "Multiple faces plus phone signal justify escalation.",
            "events": [
                ("multiple_faces", "detector", {"face_count": 2}, 2),
                ("tab_switch", "browser", {"hidden_seconds": 6}, 5),
                ("phone_detected", "manual", {"note": "demo trigger"}, 7),
            ],
        },
    ]

    for index, scenario in enumerate(scenarios):
        session = create_session(
            db,
            student_name=scenario["student_name"],
            student_email=scenario["student_email"],
            exam_id=scenario["exam"].id,
            access_code=scenario["exam"].access_code,
        )
        start_time = datetime.utcnow() - timedelta(minutes=(index + 1) * 16)
        session.started_at = start_time
        session.last_activity_at = start_time
        session.last_risk_event_at = start_time
        session.last_decay_at = start_time

        for event_type, source, details, minute_offset in scenario["events"]:
            recorded_at = start_time + timedelta(minutes=minute_offset)
            event = record_event(
                db,
                session,
                event_type=event_type,
                source=source,
                details=details,
                recorded_at=recorded_at,
            )
            event.created_at = recorded_at

        session.review_outcome = scenario["review_outcome"]
        session.review_notes = scenario["review_notes"]
        session.reviewed_by = admin
        session.reviewed_at = start_time + timedelta(minutes=12)
        _refresh_summary(db, session)

    db.commit()
    return {
        "created_sessions": len(scenarios),
        "message": "Demo sessions created successfully.",
    }
