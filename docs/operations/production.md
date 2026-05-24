# Production Operation

Use the same `esaa-core` package in production, but pin the version and keep
workspace state backed up.

## Install

```bash
python -m pip install esaa-core==0.5.0b1
```

## Bootstrap

```bash
esaa bootstrap --profile production
esaa init
esaa verify
```

The production profile installs governance files with independent QA review
enabled through `review_authorization: qa_role`.

## Operational Loop

- Back up `.roadmap/` before long runs.
- Run `esaa verify` before and after governed execution.
- Use `esaa runner metrics` to record external runner latency, token usage, and status.
- Use `esaa snapshot --before <seq>` for checkpoints.
- Use `esaa effects recover` if file effects need to be reapplied from artifacts.

Never manually edit `.roadmap/activity.jsonl` or the read models
`.roadmap/roadmap.json`, `.roadmap/issues.json`, and `.roadmap/lessons.json`.
