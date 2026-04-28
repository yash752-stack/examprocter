from types import SimpleNamespace

from backend.app.scoring import (
    compute_risk_level,
    generate_summary,
    points_for_event,
    recommended_action,
)


def test_phone_detection_is_immediately_high_impact():
    assert points_for_event("phone_detected", {}) == 70
    assert compute_risk_level(85) == "high"
    assert recommended_action("high") == "flag_for_review"


def test_summary_mentions_top_events():
    events = [
        SimpleNamespace(event_type="tab_switch"),
        SimpleNamespace(event_type="tab_switch"),
        SimpleNamespace(event_type="multiple_faces"),
    ]
    summary = generate_summary(110, "high", events)
    assert "tab_switch x2" in summary
    assert "multiple_faces x1" in summary
