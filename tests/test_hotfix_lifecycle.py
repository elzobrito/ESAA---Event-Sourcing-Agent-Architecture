from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esaa.adapters.base import AgentAdapter
from esaa.service import ESAAService
from esaa.store import parse_event_store


class HotfixLifecycleAdapter(AgentAdapter):
    agent_id = "agent-hotfix"

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def execute(self, dispatch_context: dict[str, Any]) -> dict[str, Any]:
        task = dispatch_context["task"]
        task_id = task["task_id"]
        status = task["status"]

        if task_id == "T-1000":
            return {
                "activity_event": {
                    "action": "issue.report",
                    "task_id": task_id,
                    "prior_status": "todo",
                    "issue_id": "ISS-HOTFIX",
                    "severity": "medium",
                    "title": "Done task needs hotfix path",
                    "fixes": "ISS-HOTFIX",
                    "evidence": {
                        "symptom": "hotfix workflow must be exercised",
                        "repro_steps": ["run hotfix lifecycle test"],
                    },
                }
            }

        if status == "todo":
            return {
                "activity_event": {
                    "action": "claim",
                    "task_id": task_id,
                    "prior_status": "todo",
                }
            }

        if status == "in_progress":
            return {
                "activity_event": {
                    "action": "complete",
                    "task_id": task_id,
                    "prior_status": "in_progress",
                    "issue_id": task["issue_id"],
                    "fixes": task["fixes"],
                    "verification": {"checks": ["unit", "regression"]},
                },
                "file_updates": [
                    {"path": task["outputs"]["files"][0], "content": "# hotfix\n"}
                ],
            }

        return {
            "activity_event": {
                "action": "review",
                "task_id": task_id,
                "prior_status": "review",
                "decision": "approve",
                "tasks": [task_id],
            }
        }


def test_hotfix_lifecycle_emits_issue_resolve_after_hotfix_review(contract_bundle: Path) -> None:
    service = ESAAService(contract_bundle, adapter=HotfixLifecycleAdapter())
    service.init(force=True)

    result = service.run(steps=4)

    assert result["steps_executed"] == 4
    events = parse_event_store(contract_bundle)
    actions = [event["action"] for event in events]
    assert "issue.report" in actions
    assert "hotfix.create" in actions
    assert "issue.resolve" in actions

    service.project()
    issues_view = json.loads((contract_bundle / ".roadmap" / "issues.json").read_text(encoding="utf-8"))
    assert issues_view["issues"][0]["issue_id"] == "ISS-HOTFIX"
    assert issues_view["issues"][0]["status"] == "resolved"
    assert service.verify()["verify_status"] == "ok"
