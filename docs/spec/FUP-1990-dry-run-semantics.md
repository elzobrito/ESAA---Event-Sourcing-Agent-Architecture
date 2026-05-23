# Dry-run response semantics

Task: `FUP-1990`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- Todo dry-run deve retornar status=dry_run.
- Campos simulados usam prefixo semantico claro como would_append_events.
- Nenhuma mutacao no event store ou no filesystem final.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
