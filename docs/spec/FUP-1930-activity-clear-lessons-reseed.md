# Activity clear baseline lessons policy

Task: `FUP-1930`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- activity clear deve manter LES-0001/2/3 por evento reconstruivel.
- Nenhuma edicao manual de lessons.json.
- dispatch-context apos clear deve incluir lessons ativas.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
