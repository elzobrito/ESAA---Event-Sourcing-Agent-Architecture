# CMM-1710 Production Hotfix Trace

## Purpose

The hotfix workflow must be demonstrable as an event trail, not only as isolated
unit behavior.

## Canonical Flow

The minimum flow is:

```text
issue.report -> hotfix.create -> claim -> complete -> orchestrator.file.write -> review -> issue.resolve -> verify.ok
```

The hotfix task is new work. The original done task remains immutable.

## Operating Modes

- default: temporary workspace fixture copied from the current contract files.
- explicit current workspace: `esaa scenario hotfix --current`.

Current-workspace execution is operator controlled because it appends real
events. It still uses only official service/CLI paths and never edits
`.roadmap/activity.jsonl` manually.

## Acceptance

- hotfix `complete` has at least two checks.
- `scope_patch` limits file writes.
- `issue.resolve` closes the issue projection.
- final `verify_status` is `ok`.

