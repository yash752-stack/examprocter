# ExamProcter

ExamProcter is an AI-powered remote exam integrity and risk scoring platform built as an interview-ready product demo.

One-line pitch:

> An AI-powered system that detects and prevents cheating in online exams using behavior analysis, risk scoring, warning stages, and real-time reviewer workflows.

## What makes this version stronger

The original MVP handled browser hooks, webcam analysis, and a basic admin dashboard. This upgraded pass adds more product depth:

- Role-aware login for `admin` and `invigilator`
- Exam creation module with access codes and rule configuration
- Public student exam flow backed by exam-specific rules
- Warning stages: `soft`, `strict`, `final`
- Risk decay after clean behavior
- Reviewer notes and reviewer attribution
- Risk score trend snapshots for score-over-time charts
- Filterable operations queue for review workflows

## Core product story

Problem:

- Online exams are easy to abuse with tab switching, phone use, outside help, and multiple people.
- Naive proctoring tools often create noisy false positives and a poor candidate experience.

Solution:

- Score integrity risk cumulatively instead of making a brittle binary decision.
- Escalate with soft warning -> strict warning -> flag or terminate.
- Let reviewers inspect timelines, evidence counts, and risk trends before deciding.

## Current feature set

### Student flow

- Select an exam
- Enter an access code
- Start a monitored session
- Webcam frames are sampled every 4 seconds
- Browser hooks track:
  - tab switching
  - window blur
  - copy
  - paste
  - context menu use
- Exam rules are displayed live:
  - duration
  - warning limit
  - fullscreen requirement
  - copy/paste policy
  - allowed tabs

### Detection and scoring

- OpenCV face detection
- Heuristic attention scoring
- Suspicious motion checks
- Multiple face detection
- Richer detector taxonomy
  - `looking_left`
  - `looking_right`
  - `looking_down`
  - `looking_up`
  - `looking_away_long_duration`
  - `no_face_long_duration`
- Phone detection demo trigger
- Weighted risk scoring
- Risk decay:
  - score drops by 5 every 5 clean minutes
- Evidence snapshots for reviewable events
  - multiple faces
  - no face
  - long away duration
  - phone detection when an image is provided

### Admin / invigilator flow

- Role-aware login
- Live operations dashboard
- Session filters:
  - exam
  - risk level
  - status
  - review outcome
  - high-risk only
- Review queue
- Manual review notes
- Risk score over time chart
- Event timeline inspection
- Evidence gallery with captured proof frames
- Exam creation

## Architecture

```text
Student Browser
  -> Public FastAPI routes
  -> Session-token protected event ingestion
  -> Risk engine + warning stages + decay
  -> SQLite persistence
  -> Streamlit operations dashboard
```

## Repository structure

```text
backend/app/
  auth.py
  database.py
  detectors.py
  main.py
  models.py
  schemas.py
  scoring.py
  services.py
frontend/
  streamlit_dashboard.py
static/
  exam_client.html
tests/
streamlit_app.py
```

## Demo credentials

Dashboard accounts:

- Admin
  - email: `admin@examprocter.dev`
  - password: `Admin@123`
- Invigilator
  - email: `invigilator@examprocter.dev`
  - password: `Invigilator@123`

Default exam access codes:

- `CAMPUS2026`
- `ANALYST2026`

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

In a second terminal:

```bash
source .venv/bin/activate
streamlit run streamlit_app.py
```

Or:

```bash
chmod +x start.sh
./start.sh
```

URLs:

- Student exam client: `http://localhost:8000/exam`
- FastAPI docs: `http://localhost:8000/docs`
- Streamlit dashboard: `http://localhost:8501`

## API shape

Main routes now live under `/api/v1`.

Examples:

- `POST /api/v1/auth/login`
- `GET /api/v1/public/exams`
- `POST /api/v1/public/sessions`
- `POST /api/v1/public/sessions/{id}/events`
- `GET /api/v1/dashboard/overview`
- `POST /api/v1/dashboard/exams`
- `PATCH /api/v1/dashboard/sessions/{id}/review`

## Interview-friendly metrics

- Detection accuracy
  - based on reviewer-confirmed outcomes
- False positive rate
  - based on reviewed flagged sessions
- Average risk score
- Flagged session percentage
- Evidence count per session
- Risk score over time

## Honest tradeoffs

- Face attention is still heuristic, not full head-pose estimation
- Phone detection is a demo hook, not a YOLO pipeline yet
- SQLite is used for portability; PostgreSQL is the next backend upgrade
- Real-time dashboard updates are request-refresh based, not WebSockets yet

These tradeoffs are useful in interviews because they show product prioritization and roadmap thinking.

## Next roadmap

Phase 2 upgrades that fit naturally from here:

- JWT auth
- PostgreSQL + Redis
- WebSockets for live monitoring
- YOLO-based object detection
- Face verification
- Audio analysis
- Reviewer export reports
- Exportable reports
