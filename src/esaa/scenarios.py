from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .projector import materialize
from .service import ESAAService
from .store import parse_event_store


HOTFIX_FLOW = [
    "issue.report",
    "hotfix.create",
    "claim",
    "complete",
    "orchestrator.file.write",
    "review",
    "issue.resolve",
    "verify.start",
    "verify.ok",
]


def _prepare_temp_workspace(source_root: Path) -> Path:
    target = Path(tempfile.mkdtemp(prefix="esaa-hotfix-trace-"))
    roadmap = target / ".roadmap"
    roadmap.mkdir(parents=True, exist_ok=True)
    for name in ("AGENT_CONTRACT.yaml", "agent_result.schema.json"):
        shutil.copy2(source_root / ".roadmap" / name, roadmap / name)
    return target


def _first_task_id(events: list[dict[str, Any]]) -> str:
    roadmap, _, _ = materialize(events)
    done = [task["task_id"] for task in roadmap["tasks"] if task.get("status") == "done"]
    if done:
        return sorted(done)[0]
    if roadmap["tasks"]:
        return sorted(task["task_id"] for task in roadmap["tasks"])[0]
    return "T-1000"


def _ordered_flow(events: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    index = 0
    for event in events:
        if index < len(HOTFIX_FLOW) and event["action"] == HOTFIX_FLOW[index]:
            found.append(event["action"])
            index += 1
    return found


def run_hotfix_trace(
    source_root: Path,
    target_root: Path | None = None,
    issue_id: str = "ISS-HOTFIX-TRACE",
) -> dict[str, Any]:
    workspace = target_root or _prepare_temp_workspace(source_root)
    service = ESAAService(workspace)

    if not parse_event_store(workspace):
        service.init(force=True)

    start_seq = service.verify()["last_event_seq"]
    events_before = parse_event_store(workspace)
    fixes = _first_task_id(events_before)

    issue = service.report_issue(
        fixes,
        actor="agent-qa",
        issue_id=issue_id,
        severity="medium",
        title="Demonstrable production hotfix trace",
        symptom="hotfix path must be visible as an event trail",
        repro_steps=["run esaa scenario hotfix"],
        fixes=fixes,
    )
    hotfix_task_id = f"HF-{issue_id}"
    service.claim_task(hotfix_task_id, actor="agent-hotfix")
    service.complete_task(
        hotfix_task_id,
        actor="agent-hotfix",
        checks=["unit", "regression"],
        notes="Apply deterministic hotfix trace artifact.",
        file_updates=[
            {
                "path": f"src/hotfix/{hotfix_task_id}.txt",
                "content": f"hotfix={issue_id}\nfixes={fixes}\n",
            }
        ],
        issue_id=issue_id,
        fixes=fixes,
    )
    service.review_task(hotfix_task_id, actor="agent-hotfix", decision="approve")
    verify = service.verify()

    events = parse_event_store(workspace)
    _, issues, _ = materialize(events)
    return {
        "workspace": str(workspace),
        "start_event_seq": start_seq,
        "final_event_seq": verify["last_event_seq"],
        "issue_id": issue_id,
        "hotfix_task_id": hotfix_task_id,
        "reported_event_id": issue.get("event_id"),
        "events_found": _ordered_flow(events),
        "verify_status": verify["verify_status"],
        "projection_hash_sha256": verify["projection_hash_sha256"],
        "files_touched": [f"src/hotfix/{hotfix_task_id}.txt"],
        "issues": issues["issues"],
    }
