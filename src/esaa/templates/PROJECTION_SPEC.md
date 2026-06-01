# ESAA v0.4.x — Projection + Verify (Canonical)

Source of truth: `.roadmap/activity.jsonl` (append-only).  
Materialized views: `.roadmap/roadmap.json`, `.roadmap/issues.json`, `.roadmap/lessons.json`.

## Event envelope

Each event MUST contain:

1. `schema_version`
2. `event_id`
3. `event_seq`
4. `ts`
5. `actor`
6. `action`
7. `payload`

`event_seq` is strictly monotonic and gap-free.

## Canonical vocabulary

`run.start`, `run.end`, `task.create`, `claim`, `complete`, `review`, `issue.report`, `hotfix.create`,
`issue.resolve`, `output.rejected`, `orchestrator.file.write`, `orchestrator.view.mutate`,
`verify.start`, `verify.ok`, `verify.fail`.

## Projection function

`project(events) -> (roadmap, issues, lessons)`

Rules:

1. `task.create` creates task in `todo`.
2. `claim` transitions `todo -> in_progress` and sets lock fields (`assigned_to`, `started_at`).
3. `complete` transitions `in_progress -> review` (owner only).
4. `review(approve)` transitions `review -> done`.
5. `review(request_changes)` transitions `review -> in_progress`.
6. `issue.report` opens/updates issue.
7. `hotfix.create` adds a new hotfix task; original done task remains immutable.
8. `issue.resolve` marks issue as resolved.
9. `done` is terminal and never regresses.

## Verify

`esaa verify` performs:

1. strict parse of JSONL;
2. sequence and event-id integrity checks;
3. deterministic replay;
4. canonical JSON serialization;
5. SHA-256 comparison against materialized roadmap hash.

Hash input excludes `meta.run` to avoid self-reference:

```json
{
  "schema_version": "...",
  "project": {...},
  "tasks": [...],
  "indexes": {...}
}
```

Status outcomes:

- `ok`
- `mismatch`
- `corrupted`

