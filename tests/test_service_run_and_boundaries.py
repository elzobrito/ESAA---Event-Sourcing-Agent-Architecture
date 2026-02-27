from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from esaa.adapters.base import AgentAdapter
from esaa.errors import ESAAError
from esaa.service import ESAAService
from esaa.store import load_agent_contract, load_agent_result_schema, parse_event_store
from esaa.validator import validate_agent_output


class InvalidPathAdapter(AgentAdapter):
    def __init__(self) -> None:
        self.agent_id = "agent-invalid-path"
        self._calls = 0

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def execute(self, dispatch_context: dict[str, Any]) -> dict[str, Any]:
        task = dispatch_context["task"]
        self._calls += 1
        if self._calls == 1:
            return {"activity_event": {"action": "claim", "task_id": task["task_id"], "notes": "claim"}}
        return {
            "activity_event": {
                "action": "complete",
                "task_id": task["task_id"],
                "verification": {"checks": ["ok"]},
            },
            "file_updates": [{"path": "src/evil.txt", "content": "invalid for spec"}],
        }


def test_boundaries_reject_spec_write_into_src(contract_bundle: Path) -> None:
    contract = load_agent_contract(contract_bundle)
    schema = load_agent_result_schema(contract_bundle)
    task = {
        "task_id": "T-SPEC",
        "task_kind": "spec",
        "status": "in_progress",
        "outputs": {"files": ["docs/spec/T-SPEC.md"]},
    }
    output = {
        "activity_event": {
            "action": "complete",
            "task_id": "T-SPEC",
            "verification": {"checks": ["ok"]},
        },
        "file_updates": [{"path": "src/not-allowed.txt", "content": "x"}],
    }
    with pytest.raises(ESAAError) as exc:
        validate_agent_output(output, schema, contract, task)
    assert exc.value.code == "BOUNDARY_VIOLATION"


def test_output_rejected_has_no_side_effect_files(contract_bundle: Path) -> None:
    service = ESAAService(contract_bundle, adapter=InvalidPathAdapter())
    service.init(force=True)
    result = service.run(steps=2)
    assert result["rejected"] >= 1
    assert not (contract_bundle / "src/evil.txt").exists()

    events = parse_event_store(contract_bundle)
    assert any(event["action"] == "output.rejected" for event in events)
