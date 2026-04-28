# Deployment Notes

## Option 1: Interview demo on one machine

Run:

```bash
uvicorn backend.app.main:app --reload
streamlit run streamlit_app.py
```

Use:

- `http://localhost:8000/exam` for the student experience
- `http://localhost:8501` for the admin dashboard

## Option 2: Streamlit-hosted dashboard

Use Streamlit Community Cloud for the dashboard only.

1. Push this repository to GitHub.
2. Create a new Streamlit app using `streamlit_app.py`.
3. Set `API_BASE_URL` to the backend you deploy elsewhere.
4. Make sure the backend allows CORS.

## Backend host suggestions

- Render
- Railway
- Fly.io

Start command:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Environment variables

```text
API_BASE_URL=https://your-fastapi-host
EXAMPROCTER_DB_URL=sqlite:///data/examprocter.db
```

## Talking point

If asked why Streamlit is split from the backend, the answer is simple:

> The browser exam client needs direct JavaScript hooks for tab visibility, blur events, and webcam capture. Streamlit is excellent for the admin dashboard, but the monitoring client is more reliable as a dedicated browser page backed by FastAPI.
