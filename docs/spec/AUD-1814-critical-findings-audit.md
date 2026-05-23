# AUD-1814 — Critical findings audit coverage

## Objetivo
Expandir cobertura dos checkers `src/audit/*.py` para detectar todos os
findings críticos de `docs/qa/ESAA-current-critical-analysis.md` e desta
trilha.

## Findings monitorados

| ID                          | Detecção                                              | Severidade |
|-----------------------------|--------------------------------------------------------|------------|
| R-ATOMIC-FILE-EFFECTS       | Service path escreve file_updates ANTES do append      | critical   |
| R-NON-SERIALIZABLE-APPEND   | append_events sem lock-then-revalidate-then-write      | critical   |
| R-REVIEW-ROLE-DRIFT         | _apply_review requer assigned_to sem fallback qa_role  | high       |
| R-FILE-EFFECT-ARTIFACTS     | orchestrator.file.write sem before/after sha256        | high       |
| R-RUN-PLUGIN-PARITY         | service.run não consulta load_plugin_seeds             | high       |
| R-ISSUE-REPORT-DONE-MASK    | service masking done→review em report_issue            | high       |
| R-HOTFIX-VALIDATION         | build_hotfix_event sem validação completa              | medium     |
| R-RUNNER-METRICS-DRIFT      | runner.metrics ausente em fonte canônica               | medium     |
| R-NO-BASELINE-LESSON-RESEED | init sem orchestrator.view.mutate(lessons)             | high       |

## Evidence fields

Cada finding tem:
- `id`: string como acima
- `severity`: critical | high | medium | low | info
- `title`: descrição curta
- `evidence`: dict com paths/linhas/extracts
- `recommendation`: ação sugerida

## Aggregator

`src/audit/traceability_and_report.py` agrega os checkers `contract_consistency`,
`schema_conformance`, `eventstore_integrity` E o novo `critical_findings`. O
relatório consolidado ordena por severidade.

## Acceptance

- 9 findings monitorados, cada um com test fixture
- Regression: removendo a correção, finding correspondente reaparece
- pytest 100% verde
- `esaa verify` ok
