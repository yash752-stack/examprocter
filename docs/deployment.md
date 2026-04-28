# Deployment Notes

## Streamlit Community Cloud

The root `requirements.txt` is intentionally lightweight so Streamlit Community Cloud can boot the reviewer dashboard quickly.

Default hosted behavior:

- If `API_BASE_URL` is blank or unset, the app runs in embedded demo mode.
- Embedded demo mode uses the same SQLite models and seeds reviewable sessions automatically.
- This means the dashboard, metrics, review queue, and evidence gallery all work on Streamlit Cloud without a separate backend process.

To connect the dashboard to a live FastAPI deployment later, add:

```text
API_BASE_URL=https://your-fastapi-host
```

Once that variable is set, the sidebar switches from embedded demo mode to remote API mode.

## Full local demo mode

Install the full stack:

```bash
pip install -r requirements-backend.txt
```

Run the backend:

```bash
uvicorn backend.app.main:app --reload
```

Run the dashboard:

```bash
API_BASE_URL=http://localhost:8000 streamlit run streamlit_app.py
```

Use:

- `http://localhost:8000/exam` for the student console
- `http://localhost:8501` for the operations dashboard

Recommended split for the full product:

- Backend: Render, Railway, Fly.io
- Dashboard: Streamlit Community Cloud

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
