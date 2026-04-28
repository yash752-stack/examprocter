from __future__ import annotations

import base64
from dataclasses import dataclass
from math import sqrt
from typing import Any

import cv2
import numpy as np

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

SESSION_STATE: dict[str, dict[str, Any]] = {}
FRAME_INTERVAL_SECONDS = 4


@dataclass
class FrameAnalysis:
    face_count: int
    attention_score: float
    motion_score: float
    center_offset: float
    attention_direction: str
    suspicious_events: list[tuple[str, dict[str, Any]]]


def _decode_image(image_base64: str) -> np.ndarray:
    encoded = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    raw_bytes = base64.b64decode(encoded)
    buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode the incoming frame.")
    return frame


def _state_for_session(session_id: str) -> dict[str, Any]:
    return SESSION_STATE.setdefault(
        session_id,
        {
            "previous_frame": None,
            "away_streak": 0,
            "no_face_streak": 0,
            "long_away_emitted": False,
            "long_no_face_emitted": False,
            "last_direction": "center",
        },
    )


def _infer_attention_direction(
    face_center_x: float,
    face_center_y: float,
    frame_width: int,
    frame_height: int,
) -> str:
    normalized_x = (face_center_x - (frame_width / 2)) / (frame_width / 2)
    normalized_y = (face_center_y - (frame_height / 2)) / (frame_height / 2)

    if normalized_y > 0.18 and abs(normalized_y) >= abs(normalized_x):
        return "down"
    if normalized_y < -0.18 and abs(normalized_y) >= abs(normalized_x):
        return "up"
    if normalized_x < -0.2:
        return "left"
    if normalized_x > 0.2:
        return "right"
    return "center"


def _direction_event(direction: str) -> str:
    return {
        "left": "looking_left",
        "right": "looking_right",
        "down": "looking_down",
        "up": "looking_up",
    }.get(direction, "looking_away")


def analyze_frame(session_id: str, image_base64: str) -> FrameAnalysis:
    frame = _decode_image(image_base64)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_height, frame_width = gray.shape
    state = _state_for_session(session_id)

    faces = FACE_CASCADE.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
    )

    face_count = len(faces)
    motion_score = 0.0
    attention_score = 0.0
    center_offset = 1.0
    attention_direction = "unknown"
    suspicious_events: list[tuple[str, dict[str, Any]]] = []

    previous_frame = state.get("previous_frame")
    if previous_frame is not None and previous_frame.shape == gray.shape:
        diff = cv2.absdiff(previous_frame, gray)
        motion_score = float(np.mean(diff))

    if face_count == 0:
        state["no_face_streak"] += 1
        state["away_streak"] = 0
        state["long_away_emitted"] = False
        attention_direction = "missing"
        suspicious_events.append(("no_face_detected", {"face_count": 0}))
        if state["no_face_streak"] >= 2 and not state["long_no_face_emitted"]:
            suspicious_events.append(
                (
                    "no_face_long_duration",
                    {
                        "streak_frames": state["no_face_streak"],
                        "estimated_seconds": state["no_face_streak"] * FRAME_INTERVAL_SECONDS,
                    },
                )
            )
            state["long_no_face_emitted"] = True
    else:
        state["no_face_streak"] = 0
        state["long_no_face_emitted"] = False

        largest_face = max(faces, key=lambda face: face[2] * face[3])
        x, y, w, h = largest_face
        face_center_x = x + (w / 2)
        face_center_y = y + (h / 2)
        center_offset = sqrt(
            ((face_center_x - (frame_width / 2)) / frame_width) ** 2
            + ((face_center_y - (frame_height / 2)) / frame_height) ** 2
        )
        attention_score = max(0.0, min(1.0, 1.0 - (center_offset * 2.4)))
        attention_direction = _infer_attention_direction(
            face_center_x=face_center_x,
            face_center_y=face_center_y,
            frame_width=frame_width,
            frame_height=frame_height,
        )

        if face_count > 1:
            suspicious_events.append(("multiple_faces", {"face_count": face_count}))

        if attention_score < 0.45:
            state["away_streak"] += 1
            event_type = _direction_event(attention_direction)
            suspicious_events.append(
                (
                    event_type,
                    {
                        "attention_score": round(attention_score, 2),
                        "center_offset": round(center_offset, 2),
                        "direction": attention_direction,
                    },
                )
            )
            if state["away_streak"] >= 3 and not state["long_away_emitted"]:
                suspicious_events.append(
                    (
                        "looking_away_long_duration",
                        {
                            "attention_score": round(attention_score, 2),
                            "direction": attention_direction,
                            "streak_frames": state["away_streak"],
                            "estimated_seconds": state["away_streak"] * FRAME_INTERVAL_SECONDS,
                        },
                    )
                )
                state["long_away_emitted"] = True
        else:
            state["away_streak"] = 0
            state["long_away_emitted"] = False

    if motion_score > 25:
        suspicious_events.append(
            ("suspicious_motion", {"motion_score": round(motion_score, 2)})
        )

    state["previous_frame"] = gray
    state["last_direction"] = attention_direction

    return FrameAnalysis(
        face_count=face_count,
        attention_score=round(attention_score, 2),
        motion_score=round(motion_score, 2),
        center_offset=round(center_offset, 2),
        attention_direction=attention_direction,
        suspicious_events=suspicious_events,
    )
