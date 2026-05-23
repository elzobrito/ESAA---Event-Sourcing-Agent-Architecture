# Run plugin dispatch parity contract

Task: `FUP-1940`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- run deve usar a mesma visao efetiva de eligible.
- Tarefa de plugin late deve receber task.create antes do claim.
- Dependencias, cooldown e parallel_groups continuam respeitados.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
