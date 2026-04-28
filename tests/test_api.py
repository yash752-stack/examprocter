import os
from pathlib import Path

os.environ["EXAMPROCTER_DB_URL"] = "sqlite:////tmp/examprocter_test.db"

from fastapi.testclient import TestClient

from backend.app.database import Base, engine
from backend.app.main import app

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Path("/tmp/examprocter_test.db").unlink(missing_ok=True)


def test_session_flow_and_risk_updates():
    response = client.post(
        "/api/sessions",
        json={"student_name": "Test Candidate", "exam_name": "Interview Demo"},
    )
    assert response.status_code == 200
    session = response.json()
    assert session["risk_score"] == 0

    session_id = session["id"]
    event_response = client.post(
        f"/api/sessions/{session_id}/events",
        json={"event_type": "multiple_faces", "source": "detector", "details": {"face_count": 2}},
    )
    assert event_response.status_code == 200
    payload = event_response.json()
    assert payload["session"]["risk_score"] >= 50
    assert payload["action"] == "flag_for_review"
