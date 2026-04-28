from __future__ import annotations

from collections import Counter

EVENT_WEIGHTS = {
    "looking_away": 10,
    "multiple_faces": 50,
    "tab_switch": 30,
    "window_blur": 20,
    "copy": 12,
    "paste": 18,
    "copy_paste": 25,
    "context_menu": 15,
    "phone_detected": 70,
    "suspicious_motion": 18,
    "no_face_detected": 22,
    "webcam_offline": 35,
}

SEVERITY_BY_EVENT = {
    "looking_away": "low",
    "multiple_faces": "high",
    "tab_switch": "medium",
    "window_blur": "medium",
    "copy": "low",
    "paste": "medium",
    "copy_paste": "medium",
    "context_menu": "medium",
    "phone_detected": "high",
    "suspicious_motion": "medium",
    "no_face_detected": "medium",
    "webcam_offline": "high",
}


def points_for_event(event_type: str, details: dict | None = None) -> int:
    payload = details or {}
    points = EVENT_WEIGHTS.get(event_type, 5)

    if event_type == "multiple_faces":
        extra_faces = max(int(payload.get("face_count", 2)) - 2, 0)
        points += min(extra_faces * 10, 30)
    elif event_type == "looking_away":
        attention_score = float(payload.get("attention_score", 0.4))
        if attention_score < 0.25:
            points += 8
    elif event_type == "suspicious_motion":
        motion_score = float(payload.get("motion_score", 0))
        if motion_score > 35:
            points += 8
    elif event_type == "tab_switch":
        hidden_seconds = float(payload.get("hidden_seconds", 0))
        if hidden_seconds > 3:
            points += 10

    return points


def severity_for_event(event_type: str, points: int) -> str:
    if event_type in SEVERITY_BY_EVENT:
        return SEVERITY_BY_EVENT[event_type]
    if points >= 50:
        return "high"
    if points >= 20:
        return "medium"
    return "low"


def apply_score(current_score: int, points: int) -> int:
    return max(0, min(current_score + points, 200))


def compute_risk_level(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def recommended_action(risk_level: str) -> str:
    return {
        "low": "ignore",
        "medium": "warn",
        "high": "flag_for_review",
    }.get(risk_level, "ignore")


def warning_for_level(risk_level: str) -> str:
    return {
        "low": "Monitoring continues quietly.",
        "medium": "Issue a warning and continue monitoring.",
        "high": "Flag this session for admin review.",
    }.get(risk_level, "Monitoring continues quietly.")


def generate_summary(risk_score: int, risk_level: str, events: list) -> str:
    if not events:
        return "No suspicious activity detected yet."

    counts = Counter(event.event_type for event in events)
    top_events = ", ".join(f"{event_type} x{count}" for event_type, count in counts.most_common(3))
    action = recommended_action(risk_level).replace("_", " ")
    return (
        f"Risk score {risk_score} ({risk_level}). "
        f"Top signals: {top_events}. "
        f"Recommended action: {action}."
    )
