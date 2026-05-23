# CMM-1700 External Runner Telemetry

## Purpose

ESAA does not require native Anthropic, OpenAI, or Gemini adapters when the
agent is an external runner such as Claude Code, Codex, Antigravity, or another
tool that opens the project and drives `esaa-core`.

The required contract is runner telemetry: a deterministic record of the
execution cycle admitted through the Orchestrator, persisted append-only, and
aggregated by `esaa metrics`.

## Required Payload

`runner.metrics` is an Orchestrator-reserved event. The payload fields are:

- `task_id`
- `actor`
- `runner_id`
- `runner_kind`
- `model`
- `command_surface`
- `started_at`
- `ended_at`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cost_estimate`
- `status`
- `error_code`
- `correlation_id`

Unknown values are `null`. The runner must never invent token counts, latency,
model, cost, or provider-specific values.

## Invariants

- `append_events` remains the only persistence path.
- `event_seq` remains monotonic and gapless.
- read models are projections, not manual inputs.
- provider-native APIs are optional integration detail, not a CMM5 requirement.
- metrics with `null` numeric values are excluded from numeric totals.

## CLI Shape

The deterministic command is:

```text
esaa runner metrics --file runner-metrics.json
```

Individual CLI flags can also provide the same payload for CMD-friendly use.

