from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath
from typing import Any

from jsonschema import ValidationError, validate

from .errors import ESAAError
from .utils import normalize_rel_path


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern.replace("\\", "/")) for pattern in patterns)


def _validate_safe_path(path: str) -> str:
    norm = normalize_rel_path(path)
    if not norm or norm.startswith("/") or norm.startswith(".."):
        raise ESAAError("BOUNDARY_VIOLATION", f"invalid path: {path}")
    parts = PurePosixPath(norm).parts
    if any(part == ".." for part in parts):
        raise ESAAError("BOUNDARY_VIOLATION", f"path traversal forbidden: {path}")
    return norm


def validate_agent_output(
    output: dict[str, Any],
    schema: dict[str, Any],
    contract: dict[str, Any],
    task: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        validate(output, schema)
    except ValidationError as exc:
        raise ESAAError("SCHEMA_INVALID", str(exc)) from exc

    allowed_root = {"activity_event", "file_updates"}
    unknown_root = set(output.keys()) - allowed_root
    if unknown_root:
        raise ESAAError("SCHEMA_INVALID", f"unknown root keys: {sorted(unknown_root)}")

    event = output["activity_event"]
    action = event["action"]
    if action not in contract["vocabulary"]["allowed_agent_actions"]:
        raise ESAAError("UNKNOWN_ACTION", f"unknown action: {action}")

    if event["task_id"] != task["task_id"]:
        raise ESAAError("SCHEMA_INVALID", "activity_event.task_id does not match dispatched task")

    forbidden = set(contract["output_contract"]["activity_event"]["forbidden_fields"])
    found_forbidden = sorted([field for field in event.keys() if field in forbidden])
    if found_forbidden:
        raise ESAAError("SCHEMA_INVALID", f"forbidden activity_event fields: {found_forbidden}")

    if action == "complete":
        if task["task_kind"] == "impl":
            verification = event.get("verification", {})
            checks = verification.get("checks", [])
            min_checks = 2 if task.get("is_hotfix") else 1
            if len(checks) < min_checks:
                raise ESAAError(
                    "WORKFLOW_GATE",
                    f"complete requires at least {min_checks} verification checks",
                )
        if task.get("is_hotfix"):
            if not event.get("issue_id") or not event.get("fixes"):
                raise ESAAError("WORKFLOW_GATE", "hotfix complete requires issue_id and fixes")

    if action == "review":
        decision = event.get("decision")
        if decision not in {"approve", "request_changes"}:
            raise ESAAError("SCHEMA_INVALID", f"invalid review decision: {decision}")

    updates = list(output.get("file_updates", []))
    _validate_boundaries(updates, contract, task)
    return event, updates


def _validate_boundaries(updates: list[dict[str, str]], contract: dict[str, Any], task: dict[str, Any]) -> None:
    boundaries = contract["boundaries"]["by_task_kind"][task["task_kind"]]
    allowlist = boundaries["write"]
    denylist = boundaries.get("forbidden_write", [])

    scope_patch_enabled = contract["boundaries"]["patch_scope"]["enabled"]
    scope_patch = task.get("scope_patch", [])

    for item in updates:
        path = _validate_safe_path(item["path"])
        if not _matches_any(path, allowlist):
            raise ESAAError("BOUNDARY_VIOLATION", f"path not allowed for {task['task_kind']}: {path}")
        if denylist and _matches_any(path, denylist):
            raise ESAAError("BOUNDARY_VIOLATION", f"path explicitly forbidden: {path}")

        if scope_patch_enabled and task.get("is_hotfix"):
            if not scope_patch:
                raise ESAAError("BOUNDARY_VIOLATION", "hotfix task missing scope_patch")
            if not any(path.startswith(normalize_rel_path(prefix)) for prefix in scope_patch):
                raise ESAAError("BOUNDARY_VIOLATION", f"path outside scope_patch: {path}")

