# FUP-1942 QA

Evidence:

- `tests/test_run_plugin_dispatch_parity.py`
- `tests/test_post_survey_fixes.py::test_run_consumes_late_plugin_task`

Result: a roadmap plugin added after init is visible to `eligible` and consumed
by `run` through deterministic `task.create` admission.
