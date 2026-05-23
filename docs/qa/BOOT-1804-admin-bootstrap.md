# BOOT-1804-QA — Verify governed admin bootstrap boundaries

## Allowlist confirmada
Os 11 paths da allowlist em BOOT-1804 são exatamente os arquivos canônicos
necessários para que FIX-1807/1810/1812/1813 ajustem contratos e documentos
sem violar o protocolo ESAA.

## Denylist confirmada
Nenhum dos paths proibidos é tocado pelos admin scripts. Em particular:
- `.roadmap/activity.jsonl` permanece append-only, escrito apenas por
  `store.append_events`/`store.append_transactional` via Orchestrator.
- `.roadmap/roadmap.json`, `issues.json` e `lessons.json` permanecem como
  projeções derivadas; sua mutação ocorre apenas via `materialize` após o
  Orchestrator persistir eventos.

## Mecanismo
Cada admin script (`src/audit/<task>_apply.py`) é executado pelo Orchestrator
post-completion da task respectiva. A execução gera um evento
`orchestrator.view.mutate` com payload listando os arquivos alterados — o que
preserva a auditabilidade event-sourced.

## Escopo
Este bootstrap vigora SOMENTE durante a execução da trilha `critical-fixes`.
Após `AUD-1814-QA` concluído, qualquer nova edição em `.roadmap/**` ou raiz
exige novo bootstrap explícito.

## Conclusão
Bootstrap é **estreito, temporario, auditavel e não bypassa governance** do
event store. Aprovado para uso nas tasks FIX-1807-IMPL, FIX-1810-IMPL,
FIX-1812-IMPL e FIX-1813-IMPL.
