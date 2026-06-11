"""AUD-1814-QA — Critical findings audit coverage test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.audit.critical_findings import (
    CHECKS,
    check_baseline_lessons_reseed,
    check_done_in_prior_status,
    check_dry_run_semantics,
    check_file_effects_module,
    check_hotfix_validation,
    check_plugin_dispatch_parity,
    check_review_role,
    check_runner_metrics,
    check_serializable_append,
    main,
    run_checks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_checks_pass_against_repo():
    """Apos a trilha critical-fixes, todos os checkers devem retornar [].

    Esta e a regressao final: se algum dos R-* findings reaparece, sinaliza
    drift no engine ou nos contratos.
    """
    result = run_checks(REPO_ROOT)
    assert result["total_findings"] == 0, "findings esperados=[]; got=" + json.dumps(
        result["findings"], indent=2
    )


def test_runner_metrics_check_returns_empty():
    assert check_runner_metrics(REPO_ROOT) == []


def test_baseline_lessons_check_returns_empty():
    assert check_baseline_lessons_reseed(REPO_ROOT) == []


def test_review_role_check_returns_empty():
    assert check_review_role(REPO_ROOT) == []


def test_serializable_append_check_returns_empty():
    assert check_serializable_append(REPO_ROOT) == []


def test_file_effects_check_returns_empty():
    assert check_file_effects_module(REPO_ROOT) == []


def test_hotfix_validation_check_returns_empty():
    assert check_hotfix_validation(REPO_ROOT) == []


def test_done_prior_status_check_returns_empty():
    assert check_done_in_prior_status(REPO_ROOT) == []


def test_plugin_dispatch_check_returns_empty():
    assert check_plugin_dispatch_parity(REPO_ROOT) == []


def test_dry_run_semantics_check_returns_empty():
    assert check_dry_run_semantics(REPO_ROOT) == []


def test_checks_registry_size():
    """Garante que todos os checkers criticos estao registrados."""
    assert len(CHECKS) == 9


def test_main_returns_zero_against_repo(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["critical_findings.py", "--root", str(REPO_ROOT)])

    assert main() == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_findings"] == 0


def test_main_returns_one_when_findings_exist(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["critical_findings.py", "--root", str(tmp_path)])

    assert main() == 1
    data = json.loads(capsys.readouterr().out)
    assert data["total_findings"] > 0
