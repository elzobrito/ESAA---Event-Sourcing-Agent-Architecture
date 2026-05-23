# FUP-1922 QA

Evidence:

- `tests/test_issue_report_done_command.py`
- `tests/test_post_survey_fixes.py::test_issue_report_command_preserves_done_prior_status`

Result: `issue.report` over `done` preserves `prior_status=done` and leaves the
original task immutable.
