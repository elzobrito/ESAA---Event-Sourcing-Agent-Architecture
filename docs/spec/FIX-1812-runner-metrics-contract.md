# FIX-1812 — runner.metrics reserved action contract

## Contexto
External runners (Claude Code, Codex, Antigravity) emitem telemetria de
execução que precisa ser registrada como evento auditável no event store.
Hoje não há ação canônica reservada para isso; runners gravam em logs
externos sem auditoria event-sourced.

## Acao reservada

`runner.metrics` é adicionado ao vocabulário **reservado ao Orchestrator**.
Nunca aparece em `allowed_agent_actions`.

### Payload minimo

```json
{
  "runner_id": "claude-code-v2",
  "task_id": "<task_id ou null>",
  "metrics": {
    "tokens_input": 1234,
    "tokens_output": 567,
    "duration_ms": 8900,
    "model": "claude-...",
    "session_id": "..."
  }
}
```

## Documentos a atualizar

- `.roadmap/AGENT_CONTRACT.yaml` → `vocabulary.reserved_orchestrator_actions`
- `.roadmap/ORCHESTRATOR_CONTRACT.yaml` → `roles.orchestrator.reserved_actions`
- `src/esaa/constants.py` → `CANONICAL_ACTIONS`
- `AGENTS.md`, `.claude/CLAUDE.md`, `readme.md` → seção de vocabulário

## Audit drift

`src/audit/contract_consistency.py` ganha check: `runner.metrics` deve aparecer
em TODAS as fontes canônicas; ausência em qualquer fonte → finding
`R-RUNNER-METRICS-DRIFT`.

## Forbidden para agentes

`agent_result.schema.json` `activity_event.properties.action.enum` permanece
sem `runner.metrics`. Tentativa de agente emitir → `UNKNOWN_ACTION`.
