# Done Evidence Quality Policy

A task in `done` must have a complete governed evidence trail:

- `claim` by the owner actor;
- `complete` with `verification.checks`;
- `review` with `decision=approve`;
- for hotfix tasks, an `issue.resolve` event tied to the hotfix task.

Audit tooling should report `R-DONE-EVIDENCE-MISSING` when a done task lacks any
of these events.
