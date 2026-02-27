from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compat import normalize_legacy_event
from .constants import (
    AGENT_CONTRACT_PATH,
    AGENT_RESULT_SCHEMA_PATH,
    CANONICAL_ACTIONS,
    EVENT_STORE_PATH,
    ISSUES_PATH,
    LESSONS_PATH,
    ROADMAP_PATH,
)
from .errors import CorruptedStoreError, ESAAError
from .utils import ensure_parent


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_roadmap(root: Path) -> dict[str, Any] | None:
    path = root / ROADMAP_PATH
    if not path.exists():
        return None
    return _read_json(path)


def save_roadmap(root: Path, roadmap: dict[str, Any]) -> None:
    _write_json(root / ROADMAP_PATH, roadmap)


def save_issues(root: Path, issues_view: dict[str, Any]) -> None:
    _write_json(root / ISSUES_PATH, issues_view)


def save_lessons(root: Path, lessons_view: dict[str, Any]) -> None:
    _write_json(root / LESSONS_PATH, lessons_view)


def ensure_event_store(root: Path) -> Path:
    path = root / EVENT_STORE_PATH
    ensure_parent(path)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def parse_event_store(root: Path) -> list[dict[str, Any]]:
    path = ensure_event_store(root)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    last_seq = 0

    for idx, line in enumerate(lines, start=1):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorruptedStoreError("JSONL_INVALID", f"invalid JSON at line {idx}: {exc}") from exc

        event = normalize_legacy_event(raw)

        if not isinstance(event.get("event_seq"), int):
            raise CorruptedStoreError("EVENT_SEQ_INVALID", f"event_seq missing/invalid at line {idx}")
        if event["event_seq"] != last_seq + 1:
            raise CorruptedStoreError(
                "EVENT_SEQ_NON_MONOTONIC",
                f"expected event_seq={last_seq + 1}, got {event['event_seq']}",
            )
        last_seq = event["event_seq"]

        if "event_id" not in event:
            event["event_id"] = f"LEGACY-EV-{event['event_seq']:08d}"
        if event["event_id"] in seen_ids:
            raise CorruptedStoreError("EVENT_ID_DUPLICATE", f"duplicate event_id {event['event_id']}")
        seen_ids.add(event["event_id"])

        required = ("schema_version", "event_id", "event_seq", "ts", "actor", "action", "payload")
        missing = [k for k in required if k not in event]
        if missing:
            raise CorruptedStoreError("EVENT_MISSING_FIELDS", f"missing fields: {', '.join(missing)}")

        if event["action"] not in CANONICAL_ACTIONS:
            raise CorruptedStoreError("UNKNOWN_ACTION", f"unknown action in event store: {event['action']}")

        events.append(event)

    return events


def append_events(root: Path, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    path = ensure_event_store(root)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def next_event_seq(events: list[dict[str, Any]]) -> int:
    if not events:
        return 1
    return int(events[-1]["event_seq"]) + 1


def load_agent_contract(root: Path) -> dict[str, Any]:
    import yaml

    path = root / AGENT_CONTRACT_PATH
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_agent_result_schema(root: Path) -> dict[str, Any]:
    path = root / AGENT_RESULT_SCHEMA_PATH
    return _read_json(path)


def require_task(roadmap: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in roadmap.get("tasks", []):
        if task.get("task_id") == task_id:
            return task
    raise ESAAError("TASK_NOT_FOUND", f"task_id not found: {task_id}")

