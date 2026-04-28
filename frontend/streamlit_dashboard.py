from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

from frontend.embedded_backend import initialize_demo_data, request as embedded_request, resolve_asset_path

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "")
DEMO_ACCOUNTS = [
    ("Admin", "admin@examprocter.dev", "Admin@123"),
    ("Invigilator", "invigilator@examprocter.dev", "Invigilator@123"),
]


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #0f172a;
            --panel: #f8fafc;
            --accent: #ea580c;
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

        .chip-low {
            background: #dcfce7;
            color: #166534;
        }

        .chip-medium {
            background: #ffedd5;
            color: #c2410c;
        }

        .chip-high {
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
    params: dict[str, Any] | None = None,
    auth_required: bool = True,
) -> dict[str, Any] | list[dict[str, Any]]:
    if _using_embedded_mode():
        return embedded_request(
            method,
            path,
            payload=payload,
            params=params,
            current_user=st.session_state.get("current_user"),
            auth_required=auth_required,
        )

    base_url = st.session_state.api_base_url.rstrip("/")
    headers: dict[str, str] = {}
    token = st.session_state.get("auth_token")
    if auth_required and token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.request(
        method=method,
        url=f"{base_url}{path}",
        json=payload,
        params=params,
        headers=headers,
        timeout=20,
    )
    if response.status_code == 401 and auth_required:
        st.session_state.auth_token = None
        st.session_state.current_user = None
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


def _humanize_event_type(event_type: str) -> str:
    return event_type.replace("_", " ").title()


def _asset_url(file_url: str) -> str:
    if _using_embedded_mode():
        return resolve_asset_path(file_url)
    base_url = st.session_state.api_base_url.rstrip("/")
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url
    return f"{base_url}{file_url}"


def _using_embedded_mode() -> bool:
    return not st.session_state.get("api_base_url", "").strip()


def _logout() -> None:
    st.session_state.auth_token = None
    st.session_state.current_user = None


def _render_login() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>ExamProcter Operations Login</h1>
            <p>Sign in as an admin or invigilator to manage exams, review flagged sessions,
            and track integrity metrics over time.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1.1, 0.9])
    with cols[0]:
        with st.form("login_form"):
            email = st.text_input("Email", value="admin@examprocter.dev")
            password = st.text_input("Password", type="password", value="Admin@123")
            submitted = st.form_submit_button("Log in", use_container_width=True)
            if submitted:
                try:
                    result = _api_request(
                        "POST",
                        "/api/v1/auth/login",
                        payload={"email": email, "password": password},
                        auth_required=False,
                    )
                    st.session_state.auth_token = result["access_token"]
                    st.session_state.current_user = result["user"]
                    st.rerun()
                except Exception as exc:
                    st.error(f"Login failed: {exc}")
    with cols[1]:
        st.subheader("Demo accounts")
        for role, email, password in DEMO_ACCOUNTS:
            st.code(f"{role}\n{email}\n{password}")
        if _using_embedded_mode():
            st.info(
                "Streamlit deployment mode is active. The app loads local seeded sessions so the "
                "dashboard works even without a separate FastAPI service."
            )
        else:
            st.write(
                "Remote API mode is active. This dashboard points at your FastAPI service for "
                "live review data and evidence inspection."
            )


def _render_session_header(session: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <h1>{session['student_name']} - {session['exam_name']}</h1>
            <p>{session['summary']}</p>
            <div class="session-chip chip-{session['risk_level']}">
                {session['risk_level'].upper()} RISK
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _session_label(session: dict[str, Any]) -> str:
    return (
        f"{session['student_name']} | {session['exam_name']} | "
        f"{session['risk_level'].upper()} | score {session['risk_score']}"
    )


def _build_session_params() -> dict[str, Any]:
    params: dict[str, Any] = {"only_flagged": st.session_state.only_flagged}
    if st.session_state.filter_exam_id != "all":
        params["exam_id"] = st.session_state.filter_exam_id
    if st.session_state.filter_risk_levels:
        params["risk_level"] = st.session_state.filter_risk_levels
    if st.session_state.filter_statuses:
        params["status"] = st.session_state.filter_statuses
    if st.session_state.filter_reviews:
        params["review_outcome"] = st.session_state.filter_reviews
    return params


def main() -> None:
    st.set_page_config(
        page_title="ExamProcter Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)
    st.session_state.setdefault("auth_token", None)
    st.session_state.setdefault("current_user", None)

    if _using_embedded_mode():
        initialize_demo_data()

    if not st.session_state.auth_token or not st.session_state.current_user:
        _render_login()
        return

    try:
        overview = _api_request("GET", "/api/v1/dashboard/overview")
        exams = _api_request("GET", "/api/v1/dashboard/exams")
    except Exception as exc:
        st.markdown(
            """
            <div class="hero">
                <h1>Dashboard cannot reach the remote backend</h1>
                <p>Check the FastAPI deployment URL, then reload this page. You can also clear the
                API Base URL to fall back to the built-in Streamlit demo mode.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code("uvicorn backend.app.main:app --reload", language="bash")
        if st.button("Switch to embedded demo mode", use_container_width=True):
            st.session_state.api_base_url = ""
            st.rerun()
        st.info(f"Connection error: {exc}")
        return

    exam_options = {"all": "All exams"}
    for exam in exams:
        exam_options[exam["id"]] = exam["title"]

    st.session_state.setdefault("filter_exam_id", "all")
    st.session_state.setdefault("filter_risk_levels", [])
    st.session_state.setdefault("filter_statuses", [])
    st.session_state.setdefault("filter_reviews", [])
    st.session_state.setdefault("only_flagged", False)

    with st.sidebar:
        st.title("ExamProcter")
        st.caption("Admin and invigilator operations console")
        st.text_input(
            "API Base URL",
            key="api_base_url",
            placeholder="Leave blank for Streamlit demo mode",
        )
        st.caption("Mode: `embedded demo`" if _using_embedded_mode() else "Mode: `remote API`")
        st.write(
            f"Signed in as **{st.session_state.current_user['full_name']}** "
            f"(`{st.session_state.current_user['role']}`)"
        )
        if _using_embedded_mode():
            st.info(
                "This deployment is running entirely inside Streamlit with seeded SQLite data. "
                "Add a backend URL here later if you want the dashboard to attach to a live API."
            )
        st.selectbox(
            "Exam filter",
            options=list(exam_options.keys()),
            format_func=lambda key: exam_options[key],
            key="filter_exam_id",
        )
        st.multiselect(
            "Risk levels",
            options=["low", "medium", "high"],
            key="filter_risk_levels",
        )
        st.multiselect(
            "Statuses",
            options=["active", "flagged", "terminated", "completed"],
            key="filter_statuses",
        )
        st.multiselect(
            "Review states",
            options=["pending", "confirmed_flag", "false_positive", "clean"],
            key="filter_reviews",
        )
        st.checkbox("High risk only", key="only_flagged")
        if st.button("Refresh dashboard", use_container_width=True):
            st.rerun()
        if st.session_state.current_user["role"] == "admin":
            if st.button("Seed demo data", use_container_width=True):
                try:
                    result = _api_request("POST", "/api/v1/demo/seed")
                    st.success(result["message"])
                except Exception as exc:
                    st.error(f"Could not seed data: {exc}")
        if not _using_embedded_mode():
            st.markdown(f"[Open student exam client]({st.session_state.api_base_url.rstrip('/')}/exam)")
        if st.button("Log out", use_container_width=True):
            _logout()
            st.rerun()

    sessions = _api_request(
        "GET",
        "/api/v1/dashboard/sessions",
        params=_build_session_params(),
    )

    st.markdown(
        """
        <div class="hero">
            <h1>ExamProcter Operations Center</h1>
            <p>
                Phase 1 now includes role-aware access, exam creation, warning stages,
                review notes, and risk-trend analytics so the product story reads much
                closer to a real proctoring platform.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(5)
    with metric_columns[0]:
        _metric_card("Sessions", str(overview["total_sessions"]), "All monitored sessions")
    with metric_columns[1]:
        _metric_card("Active", str(overview["active_sessions"]), "Live or still-running exams")
    with metric_columns[2]:
        _metric_card("Review pending", str(overview["review_pending"]), "Sessions awaiting decision")
    with metric_columns[3]:
        _metric_card("Flagged rate", f"{overview['flagged_session_rate']:.1f}%", "Medium/high-risk sessions")
    with metric_columns[4]:
        _metric_card("False positives", _format_rate(overview["false_positive_rate"]), "Reviewed flagged sessions")

    tabs = st.tabs(["Operations", "Review Queue", "Exam Builder", "Architecture"])

    with tabs[0]:
        split = st.columns([1.3, 1])
        with split[0]:
            st.subheader("Session monitor")
            if sessions:
                session_rows = [
                    {
                        "Student": session["student_name"],
                        "Exam": session["exam_name"],
                        "Risk score": session["risk_score"],
                        "Peak": session["risk_score_peak"],
                        "Risk level": session["risk_level"],
                        "Action": session["current_action"],
                        "Warnings": session["warning_count"],
                        "Stage": session["warning_stage"],
                        "Evidence": session["evidence_count"],
                        "Status": session["status"],
                        "Review": session["review_outcome"],
                    }
                    for session in sessions
                ]
                st.dataframe(pd.DataFrame(session_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No sessions match the current filters.")

        with split[1]:
            st.subheader("Detection metrics")
            event_breakdown = overview.get("event_breakdown", [])
            if event_breakdown:
                st.bar_chart(
                    pd.DataFrame(event_breakdown).set_index("event_type")["count"],
                    use_container_width=True,
                )
            else:
                st.info("Event distribution will appear once sessions are active.")
            st.metric("Detection accuracy", _format_rate(overview["detection_accuracy"]))
            st.metric("Average risk score", f"{overview['avg_risk_score']:.1f}")
            st.metric("Suspicious events", overview["suspicious_events"])

        if sessions:
            selected_id = st.selectbox(
                "Inspect a session",
                options=[session["id"] for session in sessions],
                format_func=lambda session_id: _session_label(
                    next(session for session in sessions if session["id"] == session_id)
                ),
            )
            selected_session = next(session for session in sessions if session["id"] == selected_id)
            _render_session_header(selected_session)

            detail_columns = st.columns(5)
            with detail_columns[0]:
                st.metric("Risk score", selected_session["risk_score"])
            with detail_columns[1]:
                st.metric("Peak risk", selected_session["risk_score_peak"])
            with detail_columns[2]:
                st.metric("Warnings", selected_session["warning_count"])
            with detail_columns[3]:
                st.metric("Evidence", selected_session["evidence_count"])
            with detail_columns[4]:
                st.metric("Attention", f"{selected_session['latest_attention_score']:.2f}")

            trend = _api_request("GET", f"/api/v1/dashboard/sessions/{selected_id}/risk-trend")
            trend_rows = trend.get("points", [])
            if trend_rows:
                trend_df = pd.DataFrame(trend_rows)
                trend_df["created_at"] = pd.to_datetime(trend_df["created_at"])
                st.subheader("Risk score over time")
                st.line_chart(
                    trend_df.set_index("created_at")["risk_score"],
                    use_container_width=True,
                )
                st.caption(
                    "Risk snapshots now include event-driven increases and clean-behavior decay points."
                )

            review_columns = st.columns([1, 1.2])
            with review_columns[0]:
                with st.form(f"review_form_{selected_id}"):
                    review_outcome = st.radio(
                        "Manual review outcome",
                        options=["pending", "confirmed_flag", "false_positive", "clean"],
                        index=["pending", "confirmed_flag", "false_positive", "clean"].index(
                            selected_session["review_outcome"]
                        ),
                        horizontal=True,
                    )
                    review_notes = st.text_area(
                        "Reviewer notes",
                        value=selected_session.get("review_notes", ""),
                        height=120,
                    )
                    if st.form_submit_button("Save review", use_container_width=True):
                        _api_request(
                            "PATCH",
                            f"/api/v1/dashboard/sessions/{selected_id}/review",
                            payload={"review_outcome": review_outcome, "notes": review_notes},
                        )
                        st.success("Review updated.")
                        st.rerun()
            with review_columns[1]:
                st.subheader("Session context")
                st.write(f"Status: `{selected_session['status']}`")
                st.write(f"Current action: `{selected_session['current_action']}`")
                st.write(f"Warning stage: `{selected_session['warning_stage']}`")
                st.write(f"Last alert: {selected_session['last_alert']}")
                if selected_session.get("reviewed_by_name"):
                    st.write(
                        f"Reviewed by **{selected_session['reviewed_by_name']}** at "
                        f"`{selected_session['reviewed_at']}`"
                    )
                st.write("Exam rules:")
                st.write(f"- Duration: {selected_session['exam_rules']['duration_minutes']} minutes")
                st.write(f"- Warning limit: {selected_session['exam_rules']['warning_limit']}")
                st.write(f"- Fullscreen required: {selected_session['exam_rules']['fullscreen_required']}")
                st.write(f"- Copy/paste allowed: {selected_session['exam_rules']['allow_copy_paste']}")
                st.write(
                    f"- Allowed tabs: {', '.join(selected_session['exam_rules']['allowed_tabs']) or 'None listed'}"
                )

            timeline = _api_request("GET", f"/api/v1/dashboard/sessions/{selected_id}/timeline")
            timeline_rows = timeline.get("events", [])
            st.subheader("Suspicious activity timeline")
            if timeline_rows:
                timeline_df = pd.DataFrame(
                    [
                        {
                            "Time": row["created_at"],
                            "Type": _humanize_event_type(row["event_type"]),
                            "Source": row["source"],
                            "Severity": row["severity"],
                            "Points": row["points"],
                            "Risk after event": row["risk_after_event"],
                            "Evidence": row["is_evidence"],
                            "Details": str(row["details"]),
                        }
                        for row in timeline_rows
                    ]
                )
                st.dataframe(timeline_df, use_container_width=True, hide_index=True)
            else:
                st.info("No suspicious activity has been logged for this session yet.")

            evidence = _api_request("GET", f"/api/v1/dashboard/sessions/{selected_id}/evidence")
            evidence_items = evidence.get("items", [])
            st.subheader("Evidence gallery")
            if evidence_items:
                gallery_columns = st.columns(3)
                for index, item in enumerate(evidence_items):
                    column = gallery_columns[index % 3]
                    with column:
                        st.image(
                            _asset_url(item["file_url"]),
                            caption=(
                                f"{item['label']} | {item['created_at']}\n"
                                f"{item['note'] or 'Captured automatically during reviewable event.'}"
                            ),
                            use_container_width=True,
                        )
                        metadata = item.get("metadata", {})
                        if metadata:
                            st.caption(", ".join(f"{key}: {value}" for key, value in metadata.items()))
            else:
                st.info("No evidence snapshots captured for this session yet.")
        else:
            st.info("No sessions yet. Create an exam or seed demo data to populate the operations view.")

    with tabs[1]:
        st.subheader("Reviewer queue")
        pending_or_severe = [
            session
            for session in sessions
            if session["review_outcome"] == "pending"
            or session["risk_level"] == "high"
            or session["status"] in {"flagged", "terminated"}
        ]
        if pending_or_severe:
            queue_df = pd.DataFrame(
                [
                    {
                        "Student": session["student_name"],
                        "Exam": session["exam_name"],
                        "Risk": session["risk_score"],
                        "Stage": session["warning_stage"],
                        "Status": session["status"],
                        "Review": session["review_outcome"],
                        "Evidence": session["evidence_count"],
                    }
                    for session in pending_or_severe
                ]
            )
            st.dataframe(queue_df, use_container_width=True, hide_index=True)
        else:
            st.success("No pending review items under the current filters.")

    with tabs[2]:
        st.subheader("Exam builder")
        exam_df = pd.DataFrame(
            [
                {
                    "Title": exam["title"],
                    "Duration": exam["duration_minutes"],
                    "Warnings": exam["warning_limit"],
                    "Fullscreen": exam["fullscreen_required"],
                    "Copy/paste": exam["allow_copy_paste"],
                    "Auto terminate": exam["auto_terminate_on_limit"],
                    "Access code": exam["access_code"],
                }
                for exam in exams
            ]
        )
        st.dataframe(exam_df, use_container_width=True, hide_index=True)

        if st.session_state.current_user["role"] != "admin":
            st.info("Only admins can create or modify exams in this phase.")
        else:
            with st.form("create_exam_form"):
                title = st.text_input("Exam title")
                description = st.text_area("Description")
                duration_minutes = st.slider("Duration (minutes)", 15, 180, 60, step=5)
                warning_limit = st.slider("Warning limit", 1, 5, 3)
                fullscreen_required = st.checkbox("Require fullscreen", value=True)
                allow_copy_paste = st.checkbox("Allow copy/paste", value=False)
                auto_terminate_on_limit = st.checkbox("Auto-terminate at final stage", value=False)
                allowed_tabs = st.text_input("Allowed tabs (comma separated)", value="Exam Portal")
                access_code = st.text_input("Access code", value="NEWEXAM2026")
                if st.form_submit_button("Create exam", use_container_width=True):
                    try:
                        _api_request(
                            "POST",
                            "/api/v1/dashboard/exams",
                            payload={
                                "title": title,
                                "description": description,
                                "duration_minutes": duration_minutes,
                                "warning_limit": warning_limit,
                                "fullscreen_required": fullscreen_required,
                                "allow_copy_paste": allow_copy_paste,
                                "auto_terminate_on_limit": auto_terminate_on_limit,
                                "allowed_tabs": [
                                    tab.strip()
                                    for tab in allowed_tabs.split(",")
                                    if tab.strip()
                                ],
                                "access_code": access_code,
                            },
                        )
                        st.success("Exam created.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not create exam: {exc}")

    with tabs[3]:
        st.subheader("Current architecture")
        if _using_embedded_mode():
            st.info(
                "This hosted build is running in Streamlit-only demo mode. For live student monitoring, "
                "deploy the FastAPI backend separately and point the API Base URL at it."
            )
        st.markdown(
            """
            ```text
            Student Browser
              -> Public FastAPI routes
              -> Session token protected monitoring events
              -> Risk scoring + warning stages + decay
              -> SQLite data store
              -> Streamlit operations dashboard
            ```
            """
        )
        st.write("What changed in this upgrade:")
        st.write("- Role-aware login for admin and invigilator users")
        st.write("- Exam creation module with rules and access codes")
        st.write("- Risk decay after clean behavior")
        st.write("- Warning stages: soft, strict, final")
        st.write("- Reviewer notes and reviewer attribution")
        st.write("- Risk score trend endpoint and chart")
        st.write("- Filterable operations queue for live review")
