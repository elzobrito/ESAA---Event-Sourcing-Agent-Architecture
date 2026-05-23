# CMM-1702 External Runner Telemetry QA

## Commands

```text
python -m pytest tests/test_external_runner_metrics.py -q
python -m esaa --root . runner metrics --file runner-metrics.json
python -m esaa --root . metrics
```

## Coverage

- valid metrics with real latency and token counts;
- unknown token and latency values preserved as `null`;
- failed runner with `error_code`;
- metrics aggregated by runner kind, model, status, and error code;
- invalid negative latency rejected;
- `verify_status=ok` after persistence.

## Conclusion

External-runner telemetry is the real CMM5 requirement for Claude Code, Codex,
and Antigravity workflows. Native provider adapters remain optional.

