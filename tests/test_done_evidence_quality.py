from __future__ import annotations

from pathlib import Path

from src.audit.traceability_and_report import check_done_evidence


def test_done_tasks_have_governed_evidence(repo_root: Path) -> None:
    assert check_done_evidence(repo_root) == []
