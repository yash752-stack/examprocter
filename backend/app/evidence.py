from __future__ import annotations

import base64
import re
from datetime import datetime
from pathlib import Path

from .database import DATA_DIR

EVIDENCE_DIR = DATA_DIR / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _extension_from_data_uri(header: str) -> str:
    if "image/png" in header:
        return "png"
    if "image/webp" in header:
        return "webp"
    return "jpg"


def _decode_image(image_base64: str) -> tuple[bytes, str]:
    if "," in image_base64:
        header, encoded = image_base64.split(",", 1)
        extension = _extension_from_data_uri(header)
    else:
        encoded = image_base64
        extension = "jpg"
    return base64.b64decode(encoded), extension


def _safe_event_slug(event_type: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", event_type.strip().lower())
    return cleaned.strip("_") or "event"


def save_evidence_image(
    *,
    session_id: str,
    event_type: str,
    image_base64: str,
    captured_at: datetime,
) -> tuple[str, str]:
    raw_bytes, extension = _decode_image(image_base64)
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S%f")
    file_name = f"{session_id}_{timestamp}_{_safe_event_slug(event_type)}.{extension}"
    file_path = EVIDENCE_DIR / file_name
    Path(file_path).write_bytes(raw_bytes)
    return file_name, f"/evidence/{file_name}"
