from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath
from typing import Any

from jsonschema import ValidationError, validate

from .errors import ESAAError
from .external_effects import task_accepts_external_path
from .state_machine import REJECT_PRIOR_MISMATCH, allowed_actions_for
from .utils import normalize_rel_path


# RF08: mensagem curta — caminho + razao, sem stack/instance dump.
def _short_validation_error(exc: ValidationError) -> str:
    path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
    msg = exc.message.splitlines()[0]
    return f"{path}: {msg[:140]}"


# R8: minimo de verification.checks por task_kind (alinhado a AGENT_CONTRACT.verification_gate).
MIN_CHECKS_BY_KIND = {"spec": 1, "impl": 1, "qa": 1, "hotfix": 2}


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern.replace("\\", "/")) for pattern in patterns)


def _validate_safe_path(path: str) -> str:
    if path.startswith("runtime://"):
        return path
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
        raise ESAAError("SCHEMA_INVALID", _short_validation_error(exc)) from exc

    allowed_root = {"activity_event", "file_updates"}
    unknown_root = set(output.keys()) - allowed_root
    if unknown_root:
        raise ESAAError("SCHEMA_INVALID", f"unknown root keys: {sorted(unknown_root)}")

    event = output["activity_event"]
    action = event["action"]
    if action not in contract["vocabulary"]["allowed_agent_actions"]:
        raise ESAAError("UNKNOWN_ACTION", f"unknown action: {action}")

    # RF07: prior_status declarado deve bater com o status real do roadmap.
    if action != "issue.report":
        declared = event.get("prior_status")
        real = task["status"]
        if declared != real:
            raise ESAAError(REJECT_PRIOR_MISMATCH, f"declared={declared} real={real}")

    if action not in allowed_actions_for(task["status"]):
        raise ESAAError("WORKFLOW_GATE_VIOLATION", f"{action} not allowed in status={task['status']}")

    if event["task_id"] != task["task_id"]:
        raise ESAAError("SCHEMA_INVALID", "task_id mismatch")

    forbidden = set(contract["output_contract"]["activity_event"]["forbidden_fields"])
    found_forbidden = sorted([field for field in event.keys() if field in forbidden])
    if found_forbidden:
        raise ESAAError("SCHEMA_INVALID", f"forbidden fields: {found_forbidden}")

    if action == "complete":
        # R8: min de verification.checks por task_kind (hotfix=2).
        kind_key = "hotfix" if task.get("is_hotfix") else task["task_kind"]
        min_checks = MIN_CHECKS_BY_KIND.get(kind_key, 1)
        verification = event.get("verification", {})
        checks = verification.get("checks", [])
        if len(checks) < min_checks:
            raise ESAAError(
                "MISSING_VERIFICATION",
                f"complete requires >= {min_checks} verification checks for kind={kind_key}",
            )
        if task.get("is_hotfix"):
            if not event.get("issue_id") or not event.get("fixes"):
                raise ESAAError("MISSING_VERIFICATION", "hotfix complete requires issue_id and fixes")

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
        if path.startswith("runtime://") and task_accepts_external_path(task, path):
            continue
        if not _matches_any(path, allowlist):
            raise ESAAError("BOUNDARY_VIOLATION", f"path not allowed for {task['task_kind']}: {path}")
        if denylist and _matches_any(path, denylist):
            raise ESAAError("BOUNDARY_VIOLATION", f"path explicitly forbidden: {path}")

        if scope_patch_enabled and task.get("is_hotfix"):
            if not scope_patch:
                raise ESAAError("BOUNDARY_VIOLATION", "hotfix task missing scope_patch")
            if not any(path.startswith(normalize_rel_path(prefix)) for prefix in scope_patch):
                raise ESAAError("BOUNDARY_VIOLATION", f"path outside scope_patch: {path}")
