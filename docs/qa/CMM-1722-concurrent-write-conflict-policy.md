# CMM-1722 Concurrent Write Conflict Policy QA

## Command

```text
python -m pytest tests/test_write_conflict_policy.py -q
```

## Matrix

| Scenario | Expected |
| --- | --- |
| same planned file | separated parallel groups |
| distinct planned files | same parallel group |
| directory prefix vs child file | conflict |
| same effective file in one wave | second complete rejected |
| hotfix outside scope | boundary validation still applies |

## Event Evidence

Effective write conflicts emit `output.rejected` with `WRITE_CONFLICT`. The
second file write is not applied, and projection verification remains `ok`.

