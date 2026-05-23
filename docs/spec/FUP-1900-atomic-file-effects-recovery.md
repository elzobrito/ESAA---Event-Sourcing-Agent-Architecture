# Atomic file effects recovery policy

Task: `FUP-1900`

## Objetivo

Esta especificacao transforma o achado do relatorio QA-1817 em contrato executavel pelo core ESAA.

## Requisitos

- Definir efeito recuperavel quando commit final falhar apos append.
- Preservar artifact content-addressed e permitir reapply idempotente.
- Diferenciar efeito registrado de efeito aplicado no workspace.

## Criterios de aceite

- O caminho feliz e os casos negativos devem ter teste automatizado.
- `python -m pytest -q` deve passar.
- `python -m esaa --root . verify` deve retornar `ok`.
- Nenhuma correcao deve escrever manualmente em `.roadmap/activity.jsonl` ou read models.
