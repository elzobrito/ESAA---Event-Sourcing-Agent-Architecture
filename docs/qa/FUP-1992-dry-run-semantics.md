# FUP-1992 QA

Evidence:

- `tests/test_dry_run_semantics.py`
- `tests/test_adapters_llm.py::test_submit_dry_run_no_persist`

Result: dry-run commands return `status=dry_run` and simulated append metadata
without mutating the event store.
