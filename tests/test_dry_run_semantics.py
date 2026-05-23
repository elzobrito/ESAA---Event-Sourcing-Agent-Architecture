from __future__ import annotations

from pathlib import Path

from test_post_survey_fixes import test_runner_metrics_dry_run_response_is_unambiguous as _runner_dry_run


def test_dry_run_response_has_explicit_status(contract_bundle: Path) -> None:
    _runner_dry_run(contract_bundle)
