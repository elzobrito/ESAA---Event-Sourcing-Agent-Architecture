from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .projector import materialize


ERROR_CODE_TO_GATE = {
    "MISSING_CLAIM": "WG-001",
    "MISSING_VERIFICATION": "WG-002",
    "MISSING_COMPLETE": "WG-002",
    "PRIOR_STATUS_MISMATCH": "WG-003",
    "LOCK_VIOLATION": "WG-004",
    "ACTION_COLLAPSE": "WG-005",
}


def _sorted_dict(counter: Counter[str] | dict[str, int]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))


def _optional_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value or 0)


def _event_metrics(payload: dict[str, Any]) -> dict[str, int]:
    metrics = payload.get("metrics", {})
    usage = payload.get("usage", {})
    out = {
        "latency_ms": _optional_int(metrics.get("latency_ms", payload.get("latency_ms", 0))),
        "input_tokens": _optional_int(usage.get("input_tokens", metrics.get("input_tokens", 0))),
        "output_tokens": _optional_int(usage.get("output_tokens", metrics.get("output_tokens", 0))),
    }
    out["total_tokens"] = _optional_int(usage.get("total_tokens", metrics.get("total_tokens", payload.get("total_tokens"))))
    if out["total_tokens"] == 0:
        out["total_tokens"] = out["input_tokens"] + out["output_tokens"]
    return out


def compute_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    events_by_action: Counter[str] = Counter()
    rejected_by_code: Counter[str] = Counter()
    gate_hits: Counter[str] = Counter()
    attempts_by_task: defaultdict[str, int] = defaultdict(int)
    latency_ms_total = 0
    tokens_total = 0
    dispatch_metrics_events = 0
    runner_events = 0
    runner_latency_ms_total = 0
    runner_tokens_total = 0
    runner_by_kind: Counter[str] = Counter()
    runner_by_model: Counter[str] = Counter()
    runner_by_status: Counter[str] = Counter()
    runner_errors_by_code: Counter[str] = Counter()

    for event in events:
        action = event["action"]
        payload = event.get("payload", {})
        events_by_action[action] += 1

        if action == "output.rejected":
            code = payload.get("error_code", "UNKNOWN")
            rejected_by_code[code] += 1
            gate = ERROR_CODE_TO_GATE.get(code)
            if gate:
                gate_hits[gate] += 1
            if payload.get("task_id"):
                attempts_by_task[payload["task_id"]] += 1

        values = _event_metrics(payload)
        if values["latency_ms"] or values["total_tokens"]:
            dispatch_metrics_events += 1
            latency_ms_total += values["latency_ms"]
            tokens_total += values["total_tokens"]

        if action == "runner.metrics":
            runner_events += 1
            runner_latency_ms_total += values["latency_ms"]
            runner_tokens_total += values["total_tokens"]
            runner_by_kind[str(payload.get("runner_kind") or "unknown")] += 1
            model = payload.get("model")
            if model:
                runner_by_model[str(model)] += 1
            runner_by_status[str(payload.get("status") or "unknown")] += 1
            if payload.get("error_code"):
                runner_errors_by_code[str(payload["error_code"])] += 1

    tasks_total = 0
    tasks_done = 0
    run_status = "unknown"
    projection_hash = None
    try:
        roadmap, _, _ = materialize(events)
        tasks_total = len(roadmap.get("tasks", []))
        tasks_done = sum(1 for task in roadmap.get("tasks", []) if task.get("status") == "done")
        run_status = roadmap.get("meta", {}).get("run", {}).get("status", "unknown")
        projection_hash = roadmap.get("meta", {}).get("run", {}).get("projection_hash_sha256")
    except Exception:
        pass

    total = len(events)
    rejected = sum(rejected_by_code.values())
    return {
        "events_total": total,
        "events_by_action": _sorted_dict(events_by_action),
        "output_rejected_by_code": _sorted_dict(rejected_by_code),
        "workflow_gate_hits": _sorted_dict(gate_hits),
        "attempts_total": rejected,
        "attempts_by_task": _sorted_dict(dict(attempts_by_task)),
        "rejection_rate": rejected / total if total else 0.0,
        "llm": {
            "dispatch_metrics_events": dispatch_metrics_events,
            "latency_ms_total": latency_ms_total,
            "tokens_total": tokens_total,
        },
        "runner": {
            "events": runner_events,
            "latency_ms_total": runner_latency_ms_total,
            "tokens_total": runner_tokens_total,
            "by_runner_kind": _sorted_dict(runner_by_kind),
            "by_model": _sorted_dict(runner_by_model),
            "by_status": _sorted_dict(runner_by_status),
            "errors_by_code": _sorted_dict(runner_errors_by_code),
        },
        "tasks": {"done": tasks_done, "total": tasks_total},
        "run_status": run_status,
        "projection_hash_sha256": projection_hash,
    }
