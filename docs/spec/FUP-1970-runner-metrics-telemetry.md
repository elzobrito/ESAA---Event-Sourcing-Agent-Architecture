# Real runner metrics telemetry contract

Task: `FUP-1970`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- runner.metrics deve registrar dados reais de runners externos.
- Metricas incluem tokens, latencia, modelo, status e task_id.
- Dry-run nao deve mutar o event store.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
