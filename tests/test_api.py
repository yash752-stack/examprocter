import os
from pathlib import Path

os.environ["EXAMPROCTER_DB_URL"] = "sqlite:////tmp/examprocter_test.db"

from fastapi.testclient import TestClient

from backend.app.database import Base, engine
from backend.app.main import app

TINY_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlTH0QAAAAASUVORK5CYII="
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Path("/tmp/examprocter_test.db").unlink(missing_ok=True)


def test_admin_can_login_and_create_exam():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@examprocter.dev", "password": "Admin@123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        create_exam = client.post(
            "/api/v1/dashboard/exams",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Systems Design Test",
                "description": "Architecture-focused screening.",
                "duration_minutes": 90,
                "warning_limit": 3,
                "fullscreen_required": True,
                "allow_copy_paste": False,
                "auto_terminate_on_limit": False,
                "allowed_tabs": ["Exam Portal"],
                "access_code": "SYS2026",
            },
        )
        assert create_exam.status_code == 200
        assert create_exam.json()["access_code"] == "SYS2026"


def test_public_session_flow_uses_exam_rules_and_session_token():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@examprocter.dev", "password": "Admin@123"},
        )
        assert login.status_code == 200
        admin_token = login.json()["access_token"]

        exams = client.get("/api/v1/public/exams")
        assert exams.status_code == 200
        exam = exams.json()[0]

        access_code = "CAMPUS2026" if exam["title"] == "Campus Hiring Assessment" else "ANALYST2026"
        session = client.post(
            "/api/v1/public/sessions",
            json={
                "student_name": "Test Candidate",
                "student_email": "candidate@example.com",
                "exam_id": exam["id"],
                "access_code": access_code,
            },
        )
        assert session.status_code == 200
        payload = session.json()
        assert payload["exam_rules"]["warning_limit"] >= 1

        event_response = client.post(
            f"/api/v1/public/sessions/{payload['id']}/events",
            headers={"X-Session-Token": payload["session_token"]},
            json={
                "event_type": "phone_detected",
                "source": "manual",
                "details": {"note": "test trigger"},
                "image_base64": TINY_PNG_DATA_URI,
            },
        )
        assert event_response.status_code == 200
        event_payload = event_response.json()
        assert event_payload["session"]["risk_score"] >= 50
        assert event_payload["session"]["warning_stage"] in {"soft", "strict", "final"}

        evidence_response = client.get(
            f"/api/v1/dashboard/sessions/{payload['id']}/evidence",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert evidence_response.status_code == 200
        evidence_items = evidence_response.json()["items"]
        assert len(evidence_items) >= 1
        assert evidence_items[0]["event_type"] == "phone_detected"
