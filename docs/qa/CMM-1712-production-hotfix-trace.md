# CMM-1712 Production Hotfix Trace QA

## Command

```text
python -m pytest tests/test_hotfix_production_trace.py -q
python -m esaa --root . scenario hotfix
```

## Expected Event Order

```text
issue.report
hotfix.create
claim
complete
orchestrator.file.write
review
issue.resolve
verify.start
verify.ok
```

## Evidence

The scenario returns `issue_id`, `hotfix_task_id`, initial/final seq, files
touched, final projection hash, and resolved issue projection.

Temporary mode is safe for CI. `--current` is available only when the operator
wants the event store itself to carry the demonstration trace.

