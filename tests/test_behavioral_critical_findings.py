from __future__ import annotations

from pathlib import Path

from src.audit.critical_findings import run_checks


def test_behavioral_critical_findings_are_clean(repo_root: Path) -> None:
    result = run_checks(repo_root)
    assert result["total_findings"] == 0
    assert result["by_check"]["plugin_dispatch_parity"] == 0
    assert result["by_check"]["dry_run_semantics"] == 0
