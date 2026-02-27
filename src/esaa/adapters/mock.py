from __future__ import annotations

from typing import Any

from .base import AgentAdapter


class MockAgentAdapter(AgentAdapter):
    def __init__(self, agent_id: str = "agent-mock") -> None:
        self.agent_id = agent_id

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def execute(self, dispatch_context: dict[str, Any]) -> dict[str, Any]:
        task = dispatch_context["task"]
        task_id = task["task_id"]
        status = task["status"]

        if status == "todo":
            return {"activity_event": {"action": "claim", "task_id": task_id, "notes": "mock claim"}}

        if status == "in_progress":
            checks = [f"mock-check:{task_id}"]
            if task.get("is_hotfix"):
                checks.append(f"mock-hotfix-check:{task_id}")

            output_file = _choose_output_file(task)
            file_updates = []
            if output_file:
                file_updates = [
                    {
                        "path": output_file,
                        "content": _build_file_content(task),
                    }
                ]

            event = {
                "action": "complete",
                "task_id": task_id,
                "notes": "mock complete",
                "verification": {"checks": checks},
            }
            if task.get("is_hotfix"):
                event["issue_id"] = task["issue_id"]
                event["fixes"] = task["fixes"]
            return {"activity_event": event, "file_updates": file_updates}

        if status == "review":
            return {
                "activity_event": {
                    "action": "review",
                    "task_id": task_id,
                    "decision": "approve",
                    "tasks": [task_id],
                    "notes": "mock review approve",
                }
            }

        return {
            "activity_event": {
                "action": "issue.report",
                "task_id": task_id,
                "issue_id": f"ISS-MOCK-{task_id}",
                "severity": "low",
                "title": "Task not actionable",
                "evidence": {
                    "symptom": f"task status is {status}",
                    "repro_steps": [f"load task {task_id}", f"check status {status}"],
                },
            }
        }


def _choose_output_file(task: dict[str, Any]) -> str:
    outputs = task.get("outputs", {}).get("files", [])
    if outputs:
        return outputs[0]
    if task["task_kind"] == "spec":
        return f"docs/spec/{task['task_id']}.md"
    if task["task_kind"] == "impl":
        return f"src/{task['task_id'].lower()}.txt"
    return f"docs/qa/{task['task_id']}.md"


def _build_file_content(task: dict[str, Any]) -> str:
    return (
        f"# {task['task_id']}\n\n"
        f"- kind: {task['task_kind']}\n"
        f"- generated_by: mock_adapter\n"
        f"- note: deterministic fixture output\n"
    )

