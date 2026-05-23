# Hotfix create validation contract

Task: `FUP-1910`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- Exigir issue existente e aberta.
- Exigir fixes apontando para task existente e done quando imutavel.
- Usar a mesma validacao no comando e no fluxo automatico issue.report.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
