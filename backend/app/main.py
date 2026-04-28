from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .detectors import analyze_frame
from .models import ExamSession, IntegrityEvent
from .schemas import (
    DashboardOverview,
    EventActionResponse,
    EventIngest,
    FrameIngest,
    IntegrityEventResponse,
    ReviewUpdate,
    SessionCreate,
    SessionResponse,
    TimelineResponse,
)
from .scoring import recommended_action, warning_for_level
from .services import build_overview, create_session, finalize_session, record_event, seed_demo_data

ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="ExamProcter API",
    version="1.0.0",
    description="AI-powered exam integrity monitoring with risk scoring and live alerts.",
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


def _get_session_or_404(db: Session, session_id: str) -> ExamSession:
    session = db.get(ExamSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _event_response(event: IntegrityEvent) -> IntegrityEventResponse:
    return IntegrityEventResponse(
        id=event.id,
        session_id=event.session_id,
        source=event.source,
        event_type=event.event_type,
        severity=event.severity,
        points=event.points,
        risk_after_event=event.risk_after_event,
        details=json.loads(event.details_json),
        created_at=event.created_at,
    )


def _session_response(session: ExamSession) -> SessionResponse:
    return SessionResponse.model_validate(session)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/exam")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/exam", include_in_schema=False)
def exam_client():
    return FileResponse(STATIC_DIR / "exam_client.html")


@app.post("/api/sessions", response_model=SessionResponse)
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    session = create_session(db, payload.student_name, payload.exam_name)
    return _session_response(session)


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    return _session_response(session)


@app.post("/api/sessions/{session_id}/events", response_model=EventActionResponse)
def ingest_event(session_id: str, payload: EventIngest, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    event = record_event(
        db,
        session=session,
        event_type=payload.event_type,
        source=payload.source,
        details=payload.details,
        points_override=payload.points,
        severity_override=payload.severity,
    )
    db.commit()
    db.refresh(session)
    db.refresh(event)
    return EventActionResponse(
        session=_session_response(session),
        event=_event_response(event),
        action=recommended_action(session.risk_level),
        alert=warning_for_level(session.risk_level),
    )


@app.post("/api/sessions/{session_id}/frames", response_model=EventActionResponse)
def ingest_frame(session_id: str, payload: FrameIngest, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    analysis = analyze_frame(session_id=session.id, image_base64=payload.image_base64)

    session.latest_face_count = analysis.face_count
    session.latest_motion_score = analysis.motion_score
    session.latest_attention_score = analysis.attention_score

    last_event = None
    for event_type, details in analysis.suspicious_events:
        last_event = record_event(
            db,
            session=session,
            event_type=event_type,
            source="detector",
            details=details,
        )

    if not analysis.suspicious_events:
        session.last_alert = "Monitoring continues quietly."

    db.commit()
    db.refresh(session)
    if last_event is not None:
        db.refresh(last_event)

    return EventActionResponse(
        session=_session_response(session),
        event=_event_response(last_event) if last_event is not None else None,
        action=recommended_action(session.risk_level),
        alert=warning_for_level(session.risk_level),
        analysis={
            "face_count": analysis.face_count,
            "attention_score": analysis.attention_score,
            "motion_score": analysis.motion_score,
            "center_offset": analysis.center_offset,
            "signals": [event_type for event_type, _ in analysis.suspicious_events],
        },
    )


@app.post("/api/sessions/{session_id}/end", response_model=SessionResponse)
def end_session(session_id: str, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    return _session_response(finalize_session(db, session))


@app.patch("/api/sessions/{session_id}/review", response_model=SessionResponse)
def update_review(session_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    session.review_outcome = payload.review_outcome
    db.commit()
    db.refresh(session)
    return _session_response(session)


@app.get("/api/dashboard/overview", response_model=DashboardOverview)
def dashboard_overview(db: Session = Depends(get_db)):
    return build_overview(db)


@app.get("/api/dashboard/sessions", response_model=list[SessionResponse])
def dashboard_sessions(db: Session = Depends(get_db)):
    sessions = db.execute(
        select(ExamSession).order_by(ExamSession.risk_score.desc(), ExamSession.last_activity_at.desc())
    ).scalars().all()
    return [_session_response(session) for session in sessions]


@app.get("/api/dashboard/sessions/{session_id}/timeline", response_model=TimelineResponse)
def session_timeline(session_id: str, db: Session = Depends(get_db)):
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


@app.post("/api/demo/seed")
def seed_demo(db: Session = Depends(get_db)):
    return seed_demo_data(db)
