from __future__ import annotations

import pytest

from esaa.errors import ESAAError
from esaa.projector import materialize
from esaa.service import make_event


def _task_payload() -> dict:
    return {
        "task_id": "T-1",
        "task_kind": "impl",
        "title": "Task",
        "description": "Task description",
        "depends_on": [],
        "targets": [],
        "outputs": {"files": ["src/T-1.txt"]},
    }


def test_complete_by_non_owner_is_rejected() -> None:
    events = [
        make_event(1, "orchestrator", "run.start", {"run_id": "RUN-1", "status": "initialized"}),
        make_event(2, "orchestrator", "task.create", _task_payload()),
        make_event(3, "agent-a", "claim", {"task_id": "T-1"}),
        make_event(
            4,
            "agent-b",
            "complete",
            {"task_id": "T-1", "verification": {"checks": ["ok"]}},
        ),
    ]
    with pytest.raises(ESAAError) as exc:
        materialize(events)
    assert exc.value.code == "NOT_LOCK_OWNER"


def test_done_is_immutable() -> None:
    events = [
        make_event(1, "orchestrator", "run.start", {"run_id": "RUN-1", "status": "initialized"}),
        make_event(2, "orchestrator", "task.create", _task_payload()),
        make_event(3, "agent-a", "claim", {"task_id": "T-1"}),
        make_event(
            4,
            "agent-a",
            "complete",
            {"task_id": "T-1", "verification": {"checks": ["ok"]}},
        ),
        make_event(
            5,
            "agent-a",
            "review",
            {"task_id": "T-1", "decision": "approve", "tasks": ["T-1"]},
        ),
        make_event(6, "agent-a", "claim", {"task_id": "T-1"}),
    ]
    with pytest.raises(ESAAError) as exc:
        materialize(events)
    assert exc.value.code == "IMMUTABLE_DONE"


def test_task_description_fallback_from_title() -> None:
    events = [
        make_event(1, "orchestrator", "run.start", {"run_id": "RUN-1", "status": "initialized"}),
        make_event(
            2,
            "orchestrator",
            "task.create",
            {
                "task_id": "T-LEGACY",
                "task_kind": "spec",
                "title": "Legacy title only",
                "depends_on": [],
                "targets": [],
                "outputs": {"files": ["docs/spec/T-LEGACY.md"]},
            },
        ),
    ]
    roadmap, _, _ = materialize(events)
    assert roadmap["tasks"][0]["description"] == "Legacy title only"
