# FIX-1807 — Independent QA review role policy

## Problema
O projetor exige `actor == assigned_to` para `review`. Isso impede QA real
(reviewer ≠ executor). Hoje o teste end-to-end usa o mesmo actor em
claim/complete/review, o que mascara a falha contratual.

## Politica

| Action     | Authorization rule                                  |
|------------|-----------------------------------------------------|
| `claim`    | qualquer agente (lock vence)                         |
| `complete` | `actor == assigned_to` (preserva ownership)          |
| `review`   | `policy.resolve_role(actor) in {"qa", "orchestrator"}` |

## Role resolution

`runtime_policy.resolve_role(actor: str) -> str | None`
- Consulta `.roadmap/agents_swarm.yaml` (se existir): `agents[<actor>].role`
- Fallback: prefixo `agent-qa*` → "qa"; outros → "agent"

## Backward-compat opcional

`RUNTIME_POLICY.yaml#review_authorization`:
- `"owner"` (default histórico): assigned_to == actor
- `"qa_role"` (novo): resolve_role(actor) == "qa"

Tests legados que usam o mesmo actor continuam passando com default `"owner"`.
A trilha critical-fixes ativa `"qa_role"` no RUNTIME_POLICY.

## Reject codes

- Não-owner em complete: `LOCK_VIOLATION` (mantém)
- Não-QA em review (sob `qa_role`): `REVIEW_ROLE_VIOLATION`

## Impacto em docs

Atualizar AGENTS.md, .claude/CLAUDE.md, readme.md, AGENT_CONTRACT.yaml para
descrever a separação executor / reviewer.
