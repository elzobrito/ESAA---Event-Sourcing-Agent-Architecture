from __future__ import annotations

from pathlib import Path

from test_post_survey_fixes import test_activity_clear_reseeds_baseline_lessons as _scenario


def test_activity_clear_reseeds_baseline_lessons(contract_bundle: Path) -> None:
    _scenario(contract_bundle)
