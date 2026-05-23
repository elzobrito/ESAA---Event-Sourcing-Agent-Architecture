# Repository hygiene policy

Task: `FUP-2010`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- Remover pyc do indice e manter caches ignorados.
- Definir politica de artifacts de file effects.
- Alinhar ou justificar versoes auxiliares.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
