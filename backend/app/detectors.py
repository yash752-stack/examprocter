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
FRAME_CACHE: dict[str, np.ndarray] = {}


@dataclass
class FrameAnalysis:
    face_count: int
    attention_score: float
    motion_score: float
    center_offset: float
    suspicious_events: list[tuple[str, dict[str, Any]]]


def _decode_image(image_base64: str) -> np.ndarray:
    encoded = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    raw_bytes = base64.b64decode(encoded)
    buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode the incoming frame.")
    return frame


def analyze_frame(session_id: str, image_base64: str) -> FrameAnalysis:
    frame = _decode_image(image_base64)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_height, frame_width = gray.shape

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
    suspicious_events: list[tuple[str, dict[str, Any]]] = []

    previous_frame = FRAME_CACHE.get(session_id)
    if previous_frame is not None and previous_frame.shape == gray.shape:
        diff = cv2.absdiff(previous_frame, gray)
        motion_score = float(np.mean(diff))

    if face_count == 0:
        suspicious_events.append(("no_face_detected", {"face_count": 0}))
    else:
        largest_face = max(faces, key=lambda face: face[2] * face[3])
        x, y, w, h = largest_face
        face_center_x = x + (w / 2)
        face_center_y = y + (h / 2)
        center_offset = sqrt(
            ((face_center_x - (frame_width / 2)) / frame_width) ** 2
            + ((face_center_y - (frame_height / 2)) / frame_height) ** 2
        )
        attention_score = max(0.0, min(1.0, 1.0 - (center_offset * 2.4)))

        if face_count > 1:
            suspicious_events.append(("multiple_faces", {"face_count": face_count}))
        if attention_score < 0.45:
            suspicious_events.append(
                (
                    "looking_away",
                    {
                        "attention_score": round(attention_score, 2),
                        "center_offset": round(center_offset, 2),
                    },
                )
            )

    if motion_score > 25:
        suspicious_events.append(
            ("suspicious_motion", {"motion_score": round(motion_score, 2)})
        )

    FRAME_CACHE[session_id] = gray

    return FrameAnalysis(
        face_count=face_count,
        attention_score=round(attention_score, 2),
        motion_score=round(motion_score, 2),
        center_offset=round(center_offset, 2),
        suspicious_events=suspicious_events,
    )
