from __future__ import annotations

from pathlib import Path

from test_external_runner_metrics import test_external_runner_metrics_are_recorded_and_aggregated as _recorded
from test_post_survey_fixes import test_runner_metrics_dry_run_response_is_unambiguous as _dry_run


def test_runner_metrics_recorded_and_aggregated(contract_bundle: Path) -> None:
    _recorded(contract_bundle)


def test_runner_metrics_dry_run_is_unambiguous(contract_bundle: Path) -> None:
    _dry_run(contract_bundle)
