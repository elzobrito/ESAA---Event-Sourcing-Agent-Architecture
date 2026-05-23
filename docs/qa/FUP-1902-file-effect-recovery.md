# FUP-1902 QA

Evidence:

- `tests/test_file_effect_recovery.py`
- `tests/test_post_survey_fixes.py::test_file_effect_can_recover_after_final_commit_failure`
- `python -m pytest -q`

Result: recovery is idempotent and restores content from the recorded artifact.
