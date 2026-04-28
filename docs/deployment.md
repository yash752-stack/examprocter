# Deployment Notes

## Local demo mode

Run the backend:

```bash
uvicorn backend.app.main:app --reload
```

Run the dashboard:

```bash
streamlit run streamlit_app.py
```

Use:

- `http://localhost:8000/exam` for the student console
- `http://localhost:8501` for the operations dashboard

## Streamlit hosting

The Streamlit app is designed as the operations console. It can be hosted independently if the FastAPI backend is deployed elsewhere.

Recommended split:

- Backend: Render, Railway, Fly.io
- Dashboard: Streamlit Community Cloud

Environment variable for Streamlit:

```text
API_BASE_URL=https://your-fastapi-host
```

## Backend start command

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Product deployment note

This project now has two traffic types:

- Public student routes under `/api/v1/public`
- Protected dashboard routes under `/api/v1/dashboard`

That split makes it easier to evolve toward:

- JWT auth
- API gateways
- rate limiting
- background workers
- WebSocket push

## Demo credentials

Dashboard login:

- `admin@examprocter.dev` / `Admin@123`
- `invigilator@examprocter.dev` / `Invigilator@123`

Default exam access codes:

- `CAMPUS2026`
- `ANALYST2026`

## Architecture talking point

If someone asks why the student client is not built in Streamlit:

> The student experience needs browser-native hooks for visibility changes, blur events, fullscreen changes, and webcam capture. Streamlit is ideal for the reviewer console, while a dedicated browser client backed by FastAPI is the safer choice for monitoring behavior in real time.
