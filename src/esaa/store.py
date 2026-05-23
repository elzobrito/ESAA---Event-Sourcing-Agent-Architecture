from __future__ import annotations

import json
import os
import time
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


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def _acquire_store_lock(path: Path, timeout: float = 10.0, retry_interval: float = 0.05) -> Path:
    lock_path = _lock_path(path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"pid={os.getpid()}\n")
            return lock_path
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise ESAAError("STORE_LOCK_TIMEOUT", f"timed out waiting for {lock_path}") from exc
            time.sleep(retry_interval)


def _release_store_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def append_events(
    root: Path,
    events: list[dict[str, Any]],
    lock_timeout: float = 10.0,
    retry_interval: float = 0.05,
) -> None:
    if not events:
        return
    path = ensure_event_store(root)
    lock_path = _acquire_store_lock(path, timeout=lock_timeout, retry_interval=retry_interval)
    try:
        # Garante separacao append-only: se o arquivo existente nao termina em
        # newline (ex.: linhas adicionadas manualmente), prepende uma quebra para
        # nao concatenar o novo evento na ultima linha (evita JSONL corrompido).
        existing = path.read_bytes()
        needs_sep = bool(existing) and not existing.endswith(b"\n")
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            if needs_sep:
                handle.write("\n")
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    finally:
        _release_store_lock(lock_path)


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


def append_transactional(
    root: Path,
    build_events_fn,
    expected_first_seq: int | None = None,
    expected_projection_hash: str | None = None,
    timeout: float = 30.0,
):
    """FIX-1806 — Serializable append: parse + validate + decide seq + append + project
    sob o mesmo lock. Elimina TOCTOU entre leitura e write.

    build_events_fn(current_events: list[dict]) -> list[dict]
        Recebe os eventos atuais (sob o lock) e devolve a lista de novos eventos
        a appendar. Deve atribuir event_seq corretos baseados em current_events.

    Raises:
        ESAAError(STALE_STATE_SEQ): expected_first_seq != next_event_seq atual
        ESAAError(STALE_STATE_HASH): expected_projection_hash != hash atual
        ESAAError(STORE_LOCK_TIMEOUT): lock nao adquirido em timeout
    Returns:
        dict com last_event_seq, projection_hash_sha256, events_appended.
    """
    from .projector import materialize  # lazy import: evita ciclo

    path = ensure_event_store(root)
    lock_path = _acquire_store_lock(path, timeout=timeout, retry_interval=0.05)
    try:
        events = parse_event_store(root)

        if expected_first_seq is not None:
            actual_next = next_event_seq(events)
            if actual_next != expected_first_seq:
                raise ESAAError(
                    "STALE_STATE_SEQ",
                    f"expected_first_seq={expected_first_seq} actual={actual_next}",
                )

        if expected_projection_hash is not None:
            cur_roadmap, _, _ = materialize(events)
            cur_hash = cur_roadmap["meta"]["run"]["projection_hash_sha256"]
            if cur_hash != expected_projection_hash:
                raise ESAAError(
                    "STALE_STATE_HASH",
                    f"expected_hash={expected_projection_hash[:12]}... actual={cur_hash[:12]}...",
                )

        new_events = build_events_fn(events)
        if not new_events:
            roadmap, _, _ = materialize(events)
            return {
                "last_event_seq": roadmap["meta"]["run"]["last_event_seq"],
                "projection_hash_sha256": roadmap["meta"]["run"]["projection_hash_sha256"],
                "events_appended": 0,
            }

        # Validacao via materialize antes de persistir
        final_roadmap, final_issues, final_lessons = materialize(events + new_events)

        # Append (reentrante sob lock atual; usa a logica de newline-guard)
        existing = path.read_bytes()
        needs_sep = bool(existing) and not existing.endswith(b"\n")
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            if needs_sep:
                handle.write("\n")
            for event in new_events:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

        save_roadmap(root, final_roadmap)
        save_issues(root, final_issues)
        save_lessons(root, final_lessons)
        return {
            "last_event_seq": final_roadmap["meta"]["run"]["last_event_seq"],
            "projection_hash_sha256": final_roadmap["meta"]["run"]["projection_hash_sha256"],
            "events_appended": len(new_events),
        }
    finally:
        _release_store_lock(lock_path)
