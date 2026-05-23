from __future__ import annotations

from pathlib import Path

from test_post_survey_fixes import test_repo_policy_allows_independent_agent_qa_review as _scenario


def test_independent_agent_qa_can_approve(tmp_path: Path, repo_root: Path) -> None:
    _scenario(tmp_path, repo_root)
