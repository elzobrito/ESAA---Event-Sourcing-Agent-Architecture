from __future__ import annotations

from typing import Any


def normalize_legacy_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize v0.3-style events into canonical v0.4 shape."""
    event = dict(raw)

    if "payload" not in event and "data" in event:
        event["payload"] = event.pop("data")
    elif "data" in event:
        event.pop("data")

    if event.get("action") == "run.init":
        event["action"] = "run.start"
        payload = event.setdefault("payload", {})
        payload.setdefault("status", "initialized")

    event.setdefault("schema_version", "0.3.0")
    return event


def normalize_legacy_verify_status(status: str) -> str:
    if status == "fail":
        return "mismatch"
    return status
