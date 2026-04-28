from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #0f172a;
            --panel: #f8fafc;
            --accent: #ea580c;
            --accent-soft: #ffedd5;
            --warning: #b91c1c;
            --muted: #475569;
            --line: #e2e8f0;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 28%),
                linear-gradient(180deg, #fffaf5 0%, #f8fafc 56%, #ffffff 100%);
        }

        .hero {
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.92);
            border-radius: 20px;
            padding: 1.25rem 1.4rem;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.06);
            margin-bottom: 1rem;
        }

        .hero h1 {
            margin: 0;
            font-size: 2rem;
            color: var(--ink);
        }

        .hero p {
            margin: 0.35rem 0 0;
            color: var(--muted);
            font-size: 1rem;
        }

        .metric-card {
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.88);
            border-radius: 18px;
            padding: 1rem;
            min-height: 112px;
        }

        .metric-card label {
            color: var(--muted);
            font-size: 0.88rem;
            display: block;
        }

        .metric-card strong {
            color: var(--ink);
            font-size: 1.7rem;
            display: block;
            margin: 0.15rem 0;
        }

        .metric-card span {
            color: #64748b;
            font-size: 0.88rem;
        }

        .session-chip {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 0.4rem;
        }

        .level-low {
            background: #dcfce7;
            color: #166534;
        }

        .level-medium {
            background: #ffedd5;
            color: #c2410c;
        }

        .level-high {
            background: #fee2e2;
            color: #b91c1c;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    base_url = st.session_state.api_base_url.rstrip("/")
    response = requests.request(
        method=method,
        url=f"{base_url}{path}",
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _metric_card(label: str, value: str, caption: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <label>{label}</label>
            <strong>{value}</strong>
            <span>{caption}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _format_rate(value: float | None) -> str:
    return "Not reviewed" if value is None else f"{value:.1f}%"


def _render_session_header(session: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <h1>{session['student_name']} - {session['exam_name']}</h1>
            <p>{session['summary']}</p>
            <div class="session-chip level-{session['risk_level']}">
                {session['risk_level'].upper()} RISK
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="ExamProcter Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)

    with st.sidebar:
        st.title("ExamProcter")
        st.caption("Admin dashboard for exam integrity operations")
        st.text_input("API Base URL", key="api_base_url")
        if st.button("Seed demo data", use_container_width=True):
            try:
                result = _api_request("POST", "/api/demo/seed")
                st.success(result["message"])
            except Exception as exc:
                st.error(f"Could not seed data: {exc}")
        st.markdown(
            f"[Open exam client]({st.session_state.api_base_url.rstrip('/')}/exam)"
        )
        if st.button("Refresh dashboard", use_container_width=True):
            st.rerun()

    try:
        overview = _api_request("GET", "/api/dashboard/overview")
        sessions = _api_request("GET", "/api/dashboard/sessions")
    except Exception as exc:
        st.markdown(
            """
            <div class="hero">
                <h1>Dashboard waiting for the backend</h1>
                <p>Run the FastAPI server first, then reload this page. The dashboard can also point
                to a deployed backend by changing the API Base URL in the sidebar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code("uvicorn backend.app.main:app --reload", language="bash")
        st.info(f"Connection error: {exc}")
        return

    st.markdown(
        """
        <div class="hero">
            <h1>AI Exam Integrity System</h1>
            <p>Problem -> MVP -> metrics -> product. This console tracks suspicious behavior,
            scores risk live, and gives reviewers a clean timeline for every flagged exam.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        _metric_card("Sessions", str(overview["total_sessions"]), "All monitored exam sessions")
    with metric_columns[1]:
        _metric_card(
            "Flagged rate",
            f"{overview['flagged_session_rate']:.1f}%",
            f"{overview['flagged_sessions']} high or medium risk sessions",
        )
    with metric_columns[2]:
        _metric_card(
            "Avg risk score",
            f"{overview['avg_risk_score']:.1f}",
            "Average risk score across all students",
        )
    with metric_columns[3]:
        _metric_card(
            "False positive rate",
            _format_rate(overview["false_positive_rate"]),
            "Computed from reviewed flagged sessions",
        )

    split = st.columns([1.35, 1])

    with split[0]:
        st.subheader("Live session table")
        if sessions:
            session_rows = [
                {
                    "Student": session["student_name"],
                    "Exam": session["exam_name"],
                    "Risk score": session["risk_score"],
                    "Risk level": session["risk_level"],
                    "Warnings": session["warning_count"],
                    "Events": session["total_events"],
                    "Status": session["status"],
                    "Review": session["review_outcome"],
                    "Last alert": session["last_alert"] or "None",
                }
                for session in sessions
            ]
            st.dataframe(pd.DataFrame(session_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No sessions yet. Use the exam client or seed the demo data.")

    with split[1]:
        st.subheader("Core metrics")
        event_breakdown = overview.get("event_breakdown", [])
        if event_breakdown:
            st.bar_chart(
                pd.DataFrame(event_breakdown).set_index("event_type")["count"],
                use_container_width=True,
            )
        else:
            st.info("Event distribution will appear once activity is recorded.")
        st.metric(
            "Detection accuracy",
            _format_rate(overview["detection_accuracy"]),
            help="Review alignment across sessions manually labeled by an admin.",
        )
        st.metric("Suspicious events", overview["suspicious_events"])

    if not sessions:
        return

    session_lookup = {
        session["id"]: f"{session['student_name']} | {session['exam_name']} | {session['risk_level'].upper()} | {session['risk_score']}"
        for session in sessions
    }
    selected_id = st.selectbox(
        "Inspect a session",
        options=list(session_lookup.keys()),
        format_func=lambda session_id: session_lookup[session_id],
    )
    selected_session = next(session for session in sessions if session["id"] == selected_id)
    _render_session_header(selected_session)

    detail_columns = st.columns(4)
    with detail_columns[0]:
        st.metric("Risk score", selected_session["risk_score"])
    with detail_columns[1]:
        st.metric("Warnings", selected_session["warning_count"])
    with detail_columns[2]:
        st.metric("Face count", selected_session["latest_face_count"])
    with detail_columns[3]:
        st.metric("Attention", f"{selected_session['latest_attention_score']:.2f}")

    review_columns = st.columns([1, 1.3])
    with review_columns[0]:
        review_options = ["pending", "confirmed_flag", "false_positive", "clean"]
        review_value = st.radio(
            "Manual review outcome",
            options=review_options,
            index=review_options.index(selected_session["review_outcome"]),
            horizontal=True,
        )
        if st.button("Save review label", use_container_width=True):
            _api_request(
                "PATCH",
                f"/api/sessions/{selected_id}/review",
                {"review_outcome": review_value},
            )
            st.success("Review label updated.")
            st.rerun()
    with review_columns[1]:
        st.write("Interview-ready metrics this supports:")
        st.write("- Detection accuracy via reviewer feedback")
        st.write("- False positive rate for flagged sessions")
        st.write("- Average risk score per student")
        st.write("- Flagged session percentage")

    timeline = _api_request("GET", f"/api/dashboard/sessions/{selected_id}/timeline")
    timeline_rows = timeline.get("events", [])
    st.subheader("Suspicious activity timeline")
    if timeline_rows:
        timeline_df = pd.DataFrame(
            [
                {
                    "Time": row["created_at"],
                    "Type": row["event_type"],
                    "Source": row["source"],
                    "Severity": row["severity"],
                    "Points": row["points"],
                    "Risk after event": row["risk_after_event"],
                    "Details": str(row["details"]),
                }
                for row in timeline_rows
            ]
        )
        st.dataframe(timeline_df, use_container_width=True, hide_index=True)
        st.bar_chart(timeline_df["Type"].value_counts(), use_container_width=True)
    else:
        st.info("No suspicious activity has been logged for this session yet.")
