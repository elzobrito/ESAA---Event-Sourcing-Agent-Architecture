from __future__ import annotations

from pathlib import Path

from test_post_survey_fixes import test_issue_report_command_preserves_done_prior_status as _scenario


def test_issue_report_done_preserves_prior_status(contract_bundle: Path) -> None:
    _scenario(contract_bundle)
