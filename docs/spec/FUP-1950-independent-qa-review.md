# Independent QA review policy

Task: `FUP-1950`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- review_authorization=qa_role e a politica efetiva.
- agent-qa deve resolver para role qa.
- Owner sem role qa deve ser rejeitado quando a politica exigir QA.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
