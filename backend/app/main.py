from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .detectors import analyze_frame
from .evidence import EVIDENCE_DIR
from .models import EvidenceSnapshot, Exam, ExamSession, IntegrityEvent, RiskSnapshot, User
from .schemas import (
    AuthLoginRequest,
    AuthLoginResponse,
    DashboardOverview,
    EvidenceGalleryResponse,
    EvidenceSnapshotResponse,
    EventActionResponse,
    EventIngest,
    ExamCreate,
    ExamPublicResponse,
    ExamResponse,
    FrameIngest,
    IntegrityEventResponse,
    ReviewUpdate,
    RiskTrendPoint,
    RiskTrendResponse,
    SessionCreate,
    SessionResponse,
    SessionStartResponse,
    TimelineResponse,
    UserResponse,
)
from .services import (
    authenticate_user,
    bootstrap_platform,
    build_overview,
    create_evidence_snapshot,
    create_exam,
    create_session,
    finalize_session,
    get_user_by_token,
    humanize_event_type,
    list_exams,
    list_evidence_for_session,
    list_sessions,
    record_event,
    review_session,
    seed_demo_data,
    serialize_allowed_tabs,
    touch_session_activity,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_platform(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="ExamProcter API",
    version="2.0.0",
    description="AI-powered exam integrity monitoring with role-aware operations, exam rules, and review workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")


def _exam_response(exam: Exam) -> ExamResponse:
    return ExamResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        warning_limit=exam.warning_limit,
        fullscreen_required=exam.fullscreen_required,
        allow_copy_paste=exam.allow_copy_paste,
        auto_terminate_on_limit=exam.auto_terminate_on_limit,
        allowed_tabs=serialize_allowed_tabs(exam),
        access_code=exam.access_code,
        created_by_name=exam.created_by.full_name if exam.created_by else None,
        created_at=exam.created_at,
    )


def _exam_public_response(exam: Exam) -> ExamPublicResponse:
    return ExamPublicResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        warning_limit=exam.warning_limit,
        fullscreen_required=exam.fullscreen_required,
        allow_copy_paste=exam.allow_copy_paste,
        auto_terminate_on_limit=exam.auto_terminate_on_limit,
        allowed_tabs=serialize_allowed_tabs(exam),
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
    )


def _event_response(event: IntegrityEvent) -> IntegrityEventResponse:
    return IntegrityEventResponse(
        id=event.id,
        session_id=event.session_id,
        source=event.source,
        event_type=event.event_type,
        severity=event.severity,
        points=event.points,
        risk_after_event=event.risk_after_event,
        is_evidence=event.is_evidence,
        details=json.loads(event.details_json),
        created_at=event.created_at,
    )


def _evidence_response(item: EvidenceSnapshot) -> EvidenceSnapshotResponse:
    return EvidenceSnapshotResponse(
        id=item.id,
        session_id=item.session_id,
        event_id=item.event_id,
        event_type=item.event_type,
        label=item.label,
        note=item.note,
        file_url=item.file_url,
        metadata=json.loads(item.metadata_json),
        created_at=item.created_at,
    )


def _session_response(session: ExamSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        exam_id=session.exam_id,
        student_name=session.student_name,
        student_email=session.student_email,
        exam_name=session.exam_name,
        status=session.status,
        risk_score=session.risk_score,
        risk_score_peak=session.risk_score_peak,
        risk_level=session.risk_level,
        warning_count=session.warning_count,
        warning_stage=session.warning_stage,
        total_events=session.total_events,
        evidence_count=session.evidence_count,
        latest_face_count=session.latest_face_count,
        latest_motion_score=session.latest_motion_score,
        latest_attention_score=session.latest_attention_score,
        current_action=session.current_action,
        last_alert=session.last_alert,
        review_outcome=session.review_outcome,
        review_notes=session.review_notes,
        reviewed_by_name=session.reviewed_by.full_name if session.reviewed_by else None,
        reviewed_at=session.reviewed_at,
        summary=session.summary,
        started_at=session.started_at,
        last_activity_at=session.last_activity_at,
        ended_at=session.ended_at,
        exam_rules=_exam_public_response(session.exam),
    )


def _session_start_response(session: ExamSession) -> SessionStartResponse:
    payload = _session_response(session).model_dump()
    payload["session_token"] = session.session_token
    return SessionStartResponse(**payload)


def _get_session_or_404(db: Session, session_id: str) -> ExamSession:
    session = db.get(ExamSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Expected a Bearer token.")
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    user = get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    return user


def require_roles(*roles: str):
    allowed_roles = set(roles)

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You do not have access to this resource.")
        return current_user

    return _dependency


def get_public_session(
    session_id: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
) -> ExamSession:
    session = _get_session_or_404(db, session_id)
    if session.session_token != x_session_token:
        raise HTTPException(status_code=401, detail="Invalid session token.")
    return session


def _evidence_note(event_type: str, details: dict[str, object]) -> str:
    pretty_name = humanize_event_type(event_type)
    if not details:
        return f"Evidence snapshot for {pretty_name.lower()}."
    if "face_count" in details:
        return f"{pretty_name} detected with {details['face_count']} visible face(s)."
    if "direction" in details:
        return f"{pretty_name} detected toward {details['direction']}."
    if "motion_score" in details:
        return f"{pretty_name} with motion score {details['motion_score']}."
    return f"Evidence snapshot for {pretty_name.lower()}."


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/exam")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/exam", include_in_schema=False)
def exam_client():
    return FileResponse(STATIC_DIR / "exam_client.html")


@app.post("/api/v1/auth/login", response_model=AuthLoginResponse)
def auth_login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return AuthLoginResponse(
        access_token=user.auth_token or "",
        user=_user_response(user),
    )


@app.get("/api/v1/auth/me", response_model=UserResponse)
def auth_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@app.get("/api/v1/public/exams", response_model=list[ExamPublicResponse])
def public_exams(db: Session = Depends(get_db)):
    return [_exam_public_response(exam) for exam in list_exams(db)]


@app.post("/api/v1/public/sessions", response_model=SessionStartResponse)
def public_start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    try:
        session = create_session(
            db,
            student_name=payload.student_name,
            student_email=payload.student_email,
            exam_id=payload.exam_id,
            access_code=payload.access_code,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _session_start_response(session)


@app.get("/api/v1/public/sessions/{session_id}", response_model=SessionResponse)
def public_get_session(
    session: ExamSession = Depends(get_public_session),
    db: Session = Depends(get_db),
):
    touch_session_activity(db, session, reason="student_refresh")
    db.commit()
    db.refresh(session)
    return _session_response(session)


@app.post("/api/v1/public/sessions/{session_id}/events", response_model=EventActionResponse)
def public_ingest_event(
    payload: EventIngest,
    session: ExamSession = Depends(get_public_session),
    db: Session = Depends(get_db),
):
    try:
        event = record_event(
            db,
            session,
            event_type=payload.event_type,
            source=payload.source,
            details=payload.details,
            points_override=payload.points,
            severity_override=payload.severity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(session)
    db.refresh(event)
    if payload.image_base64 and event.is_evidence:
        create_evidence_snapshot(
            db,
            session=session,
            event=event,
            event_type=event.event_type,
            image_base64=payload.image_base64,
            captured_at=event.created_at,
            note=_evidence_note(event.event_type, payload.details),
            metadata=payload.details,
        )
        db.commit()
        db.refresh(session)

    return EventActionResponse(
        session=_session_response(session),
        event=_event_response(event),
        action=session.current_action,
        alert=session.last_alert,
    )


@app.post("/api/v1/public/sessions/{session_id}/frames", response_model=EventActionResponse)
def public_ingest_frame(
    payload: FrameIngest,
    session: ExamSession = Depends(get_public_session),
    db: Session = Depends(get_db),
):
    analysis = analyze_frame(session_id=session.id, image_base64=payload.image_base64)
    session.latest_face_count = analysis.face_count
    session.latest_motion_score = analysis.motion_score
    session.latest_attention_score = analysis.attention_score

    last_event = None
    if analysis.suspicious_events:
        for event_type, details in analysis.suspicious_events:
            event = record_event(
                db,
                session,
                event_type=event_type,
                source="detector",
                details=details,
            )
            if event.is_evidence:
                create_evidence_snapshot(
                    db,
                    session=session,
                    event=event,
                    event_type=event.event_type,
                    image_base64=payload.image_base64,
                    captured_at=event.created_at,
                    note=_evidence_note(event.event_type, details),
                    metadata=details,
                )
            last_event = event
    else:
        touch_session_activity(db, session, reason="clean_frame")
        session.current_action = "ignore"
        session.last_alert = "Monitoring continues quietly."

    db.commit()
    db.refresh(session)
    if last_event is not None:
        db.refresh(last_event)

    return EventActionResponse(
        session=_session_response(session),
        event=_event_response(last_event) if last_event is not None else None,
        action=session.current_action,
        alert=session.last_alert,
        analysis={
            "face_count": analysis.face_count,
            "attention_score": analysis.attention_score,
            "motion_score": analysis.motion_score,
            "center_offset": analysis.center_offset,
            "attention_direction": analysis.attention_direction,
            "signals": [event_type for event_type, _ in analysis.suspicious_events],
        },
    )


@app.post("/api/v1/public/sessions/{session_id}/end", response_model=SessionResponse)
def public_end_session(
    session: ExamSession = Depends(get_public_session),
    db: Session = Depends(get_db),
):
    return _session_response(finalize_session(db, session))


@app.get("/api/v1/dashboard/overview", response_model=DashboardOverview)
def dashboard_overview(
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    return build_overview(db)


@app.get("/api/v1/dashboard/exams", response_model=list[ExamResponse])
def dashboard_exams(
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    return [_exam_response(exam) for exam in list_exams(db)]


@app.post("/api/v1/dashboard/exams", response_model=ExamResponse)
def dashboard_create_exam(
    payload: ExamCreate,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    try:
        exam = create_exam(
            db,
            title=payload.title,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            warning_limit=payload.warning_limit,
            fullscreen_required=payload.fullscreen_required,
            allow_copy_paste=payload.allow_copy_paste,
            auto_terminate_on_limit=payload.auto_terminate_on_limit,
            allowed_tabs=payload.allowed_tabs,
            access_code=payload.access_code,
            created_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _exam_response(exam)


@app.get("/api/v1/dashboard/sessions", response_model=list[SessionResponse])
def dashboard_sessions(
    exam_id: str | None = None,
    risk_level: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
    review_outcome: list[str] = Query(default=[]),
    only_flagged: bool = False,
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    sessions = list_sessions(
        db,
        exam_id=exam_id,
        risk_levels=risk_level,
        statuses=status,
        review_outcomes=review_outcome,
        only_flagged=only_flagged,
    )
    return [_session_response(session) for session in sessions]


@app.get("/api/v1/dashboard/sessions/{session_id}/timeline", response_model=TimelineResponse)
def dashboard_session_timeline(
    session_id: str,
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    events = db.execute(
        select(IntegrityEvent)
        .where(IntegrityEvent.session_id == session_id)
        .order_by(IntegrityEvent.created_at.desc())
    ).scalars().all()
    return TimelineResponse(
        session_id=session_id,
        events=[_event_response(event) for event in events],
    )


@app.get("/api/v1/dashboard/sessions/{session_id}/evidence", response_model=EvidenceGalleryResponse)
def dashboard_session_evidence(
    session_id: str,
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    items = list_evidence_for_session(db, session_id)
    return EvidenceGalleryResponse(
        session_id=session_id,
        items=[_evidence_response(item) for item in items],
    )


@app.get("/api/v1/dashboard/sessions/{session_id}/risk-trend", response_model=RiskTrendResponse)
def dashboard_session_risk_trend(
    session_id: str,
    _: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    points = db.execute(
        select(RiskSnapshot)
        .where(RiskSnapshot.session_id == session_id)
        .order_by(RiskSnapshot.created_at.asc())
    ).scalars().all()
    return RiskTrendResponse(
        session_id=session_id,
        points=[
            RiskTrendPoint(
                created_at=point.created_at,
                risk_score=point.risk_score,
                risk_level=point.risk_level,
                reason=point.reason,
            )
            for point in points
        ],
    )


@app.patch("/api/v1/dashboard/sessions/{session_id}/review", response_model=SessionResponse)
def dashboard_review_session(
    session_id: str,
    payload: ReviewUpdate,
    current_user: User = Depends(require_roles("admin", "invigilator")),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    session = review_session(
        db,
        session,
        review_outcome=payload.review_outcome,
        notes=payload.notes,
        reviewer=current_user,
    )
    return _session_response(session)


@app.post("/api/v1/demo/seed")
def seed_demo(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    return seed_demo_data(db)
