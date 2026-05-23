# FIX-1810 — Done status evidence for issue.report

## Problema
Schema `agent_result.schema.json` define `prior_status` enum como
`["todo", "in_progress", "review"]`. Mas o contrato permite `issue.report`
sobre task `done`. Como o agente declara `prior_status` para uma task done?

Hoje, `service.report_issue` (quando chamado em done) PRESERVA o status (não
mascara para review). Mas o schema bloqueia o envelope porque `prior_status`
não aceita `"done"`.

## Politica

Extender o enum de `prior_status` para incluir `"done"`. Restringir via `allOf`:
- `action=claim` → `prior_status="todo"` (já restrito)
- `action=complete` → `prior_status="in_progress"` (já restrito)
- `action=review` → `prior_status="review"` (já restrito)
- `action=issue.report` → `prior_status ∈ {todo, in_progress, review, done}` (livre)

Validator continua skipping o check de prior_status mismatch para `issue.report`
(RF07 already does this).

## Imutabilidade preservada

- `claim`/`complete`/`review` sobre task done → REJEITADO (`IMMUTABLE_DONE_VIOLATION`)
- `issue.report` sobre task done → ACEITO, status permanece `done`

## Impacto

- Schema atualizado: enum + (já existente) allOf condicional não viola outras
  branches (`claim`/`complete`/`review` continuam const-restritas).
- Docs (AGENTS.md, CLAUDE.md) atualizadas para mencionar `done` em prior_status.
