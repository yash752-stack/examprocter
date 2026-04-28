# ExamProcter

ExamProcter is an AI Exam Integrity System built to demonstrate product thinking, MVP execution, and exam-security domain fit in one interview-ready project.

One-line pitch:

> An AI-powered system that detects and prevents cheating in online exams using behavior analysis, risk scoring, and real-time alerts.

## Why this stands out

Instead of a brittle "cheating / not cheating" rule set, ExamProcter uses weighted integrity signals:

- Looking away -> +10
- Multiple faces -> +50
- Tab switch -> +30
- Phone detection -> +70
- Copy / paste / context menu -> incremental browser-risk scoring

That gives you a much better interview story:

- Problem: online exams are easy to abuse and often generate noisy false positives.
- MVP: browser hooks + webcam checks + risk engine + reviewer dashboard.
- Metrics: flagged session rate, false positive rate, detection accuracy, average risk score.
- Product: a working student console, API backend, and admin dashboard.

## MVP features

- Webcam-based frame analysis with OpenCV
  - multiple faces
  - missing face
  - likely attention drift
  - suspicious motion
- Browser activity tracking
  - tab switching
  - window blur
  - copy
  - paste
  - context menu
- Risk scoring engine
  - cumulative weighted scoring
  - low / medium / high thresholds
  - action mapping: ignore / warn / flag for review
- Admin review dashboard
  - live sessions
  - suspicious event timeline
  - reviewer labels for precision / false-positive feedback
- Demo-ready seed data

## Architecture

```text
Browser exam client (HTML + JS)
        |
        v
FastAPI backend
  - session ingestion
  - event logging
  - frame analysis
  - risk scoring
  - SQLite persistence
        |
        +--> Streamlit dashboard
```

## Repository structure

```text
backend/app/
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

## Local run

1. Create a virtual environment.
2. Install dependencies.
3. Start the FastAPI backend.
4. Start the Streamlit dashboard.

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

Or use the helper script:

```bash
chmod +x start.sh
./start.sh
```

Useful URLs:

- Exam client: `http://localhost:8000/exam`
- API docs: `http://localhost:8000/docs`
- Streamlit dashboard: `http://localhost:8501`

## Metrics you can discuss in the interview

- Detection accuracy
  - derived from reviewer feedback labels (`confirmed_flag` and `clean`)
- False positive rate
  - computed from reviewed flagged sessions
- Average risk score per student
- Flagged session percentage
- Suspicious events per session

## Streamlit hosting

This repo is set up so the Streamlit dashboard can be deployed independently.

Recommended setup:

- Deploy the FastAPI backend on Render, Railway, Fly.io, or any Python host.
- Deploy the Streamlit dashboard on Streamlit Community Cloud.
- Set `API_BASE_URL` in Streamlit to your deployed backend URL.

Streamlit entry file:

- `streamlit_app.py`

Required Streamlit secret or environment variable:

```text
API_BASE_URL=https://your-backend-url
```

## Demo flow for the interview

1. Start a session in the exam client.
2. Switch tabs once and come back.
3. Trigger the phone-detection demo control.
4. Show the risk score jump from low to medium / high.
5. Open the Streamlit dashboard.
6. Walk through the session timeline and reviewer label.
7. Quote the metrics from the dashboard.

## Honest MVP tradeoffs

- Phone detection is a demo integration hook, not a trained object detector.
- Looking-away detection is a lightweight face-center heuristic, not head-pose estimation.
- This project is optimized for demo speed, extensibility, and product clarity.

Those tradeoffs are actually useful in an interview because they show prioritization and MVP thinking.
