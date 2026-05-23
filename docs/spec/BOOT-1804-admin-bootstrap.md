# BOOT-1804 — Governed admin bootstrap for contract edits

## Contexto

Vários itens desta trilha (FIX-1807/1810/1812/1813) precisam editar arquivos
canônicos fora das boundaries dos task_kinds:
- `.roadmap/AGENT_CONTRACT.yaml`
- `.roadmap/ORCHESTRATOR_CONTRACT.yaml`
- `.roadmap/agent_result.schema.json`
- `.roadmap/roadmap.schema.json`
- `AGENTS.md`, `.claude/CLAUDE.md`, `readme.md`

Por contrato (`AGENT_CONTRACT.yaml#boundaries.by_task_kind`), o agente
NUNCA pode escrever em `.roadmap/**` ou na raiz fora de `docs/`, `src/`, `tests/`.

## Caminho explicito permitido

A trilha critical-fixes adota um **admin bootstrap restrito**:

1. O task **impl** produz um **script admin** em `src/audit/<task>_apply.py`
   (boundary `src/**` valida). O script descreve textualmente a operação.
2. Após o ciclo da task ser admitido (claim → complete → review approve), o
   **Orchestrator** executa o script sob o role administrativo, emitindo um
   evento `orchestrator.view.mutate` para auditar a mudança.
3. O script só pode escrever em paths da **allowlist abaixo**.

### Allowlist (somente estes paths)
- `.roadmap/AGENT_CONTRACT.yaml`
- `.roadmap/ORCHESTRATOR_CONTRACT.yaml`
- `.roadmap/agent_result.schema.json`
- `.roadmap/roadmap.schema.json`
- `.roadmap/issues.schema.json`
- `.roadmap/lessons.schema.json`
- `.roadmap/PARCER_PROFILE.*.yaml`
- `AGENTS.md`
- `.claude/CLAUDE.md`
- `readme.md`

### Denylist (nunca admitido por este bootstrap)
- `.roadmap/activity.jsonl` — append-only, único writer = Orchestrator
- `.roadmap/roadmap.json` — projeção, regenerada via materialize
- `.roadmap/issues.json` — projeção
- `.roadmap/lessons.json` — projeção (após R1-fix, deriva de eventos)
- `.roadmap/snapshots/**` — read-only
- `.roadmap.backup-**/**` — read-only
- Qualquer outro `.roadmap/**`

## Criterios de aceitacao

- Bootstrap é **narrow**: lista explícita, não wildcard.
- É **temporario**: só vigora durante a execução desta trilha.
- É **auditavel**: cada execução de admin script gera `orchestrator.view.mutate`.
- Não bypassa **append-only**: nenhuma escrita em `activity.jsonl` ou projeções
  via este caminho.
- Tarefas posteriores que requerem edição em `.roadmap/` ou raiz DEVEM declarar
  explicitamente o path e justificar enquadramento na allowlist.
