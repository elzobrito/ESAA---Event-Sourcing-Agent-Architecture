# Levantamento atual do ESAA apos execucao completa

Data da analise: 2026-05-23
Tarefa ESAA: QA-1817
Escopo: contratos canonicos em `.roadmap/`, harness/core em `src/esaa`, comandos CLI, event store, read models, testes, auditorias e roadmaps plugin.

## Resumo executivo

O ESAA atual esta formalmente consistente na camada deterministica: `verify` retorna `ok`, a suite de testes passa e os auditores basicos nao apontam violacoes. O event store atual estava em `last_event_seq=1347` no momento da coleta, com 108 tarefas `done`, 1 tarefa `in_progress` (`QA-1817`) e `eligible_count=0`.

Isso, porem, nao significa que todos os gaps arquiteturais foram fechados. A analise encontrou falhas semanticas que os auditores atuais nao capturam:

- A transacao de `complete + file_updates` ainda nao e atomicamente segura se a aplicacao final do arquivo falhar depois do append.
- `hotfix create` aceita hotfix orfao para issue/tarefa inexistente.
- O comando `issue report` ainda mascara `prior_status=done` como `review`.
- `activity clear` zera as lessons e nao resemeia LES-0001/2/3.
- `eligible` enxerga tarefas de plugin adicionadas apos `init`, mas `run` nao as despacha.
- A politica efetiva de review ainda e owner-review por default, nao `agent-qa` independente.
- Metricas existem, mas o event store atual nao tem `runner.metrics`; tokens/latencia reais continuam sem evidencias operacionais.
- Auditores criticos retornam zero achados mesmo com bugs reproduzidos, indicando cobertura superficial.

Conclusao: o sistema esta melhor que a versao anterior em serializacao, schema e telemetria declarativa, mas ainda nao pode ser classificado como CMM 5/Optimizing em operacao real. Ele esta mais perto de CMM 4 alto: bem controlado e verificavel, mas com lacunas de recuperacao, politica operacional e auditoria comportamental.

## Evidencias executadas

Comandos principais:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
python -m esaa --root . verify
python -m esaa --root . eligible
python -m esaa --root . metrics
python -m pytest -q
python src/audit/contract_consistency.py --root .
python src/audit/schema_conformance.py --root .
python src/audit/eventstore_integrity.py --root .
python src/audit/traceability_and_report.py --root .
python src/audit/critical_findings.py --root .
```

Resultados observados:

- `verify_status=ok`, `last_event_seq=1347`, hash `45f6be2ef2c8c3af0c86c18b6c140b8155338415c088dd1342d73dbea51b02a7`.
- `eligible_count=0`.
- `python -m pytest -q`: `146 passed`.
- Auditores formais: `contract_consistency`, `schema_conformance`, `eventstore_integrity`, `traceability_and_report` e `critical_findings` retornaram zero findings.
- `metrics`: 1347 eventos, 109 `task.create`, 109 `claim`, 108 `complete`, 108 `review`, 108 `orchestrator.file.write`, 402 `verify.start`, 402 `verify.ok`, 0 `output.rejected`, 0 gate hits, 0 `runner.metrics`.

## O que melhorou de verdade

### Lock serializavel

`src/esaa/store.py` possui `append_transactional`, com lock de filesystem, releitura do event store dentro do lock, validacao de `expected_first_seq`, validacao de projection hash esperado, append e save dos read models sob a mesma secao critica.

`src/esaa/service.py` passou a usar `_append_events_transactionally()` em `submit`, `run` e commits de eventos do Orchestrator. Isso corrige o achado anterior de lock implementado mas nao consumido pelo harness nos caminhos governados principais.

Risco residual: em caso de estado stale, o fluxo falha com `STALE_STATE_SEQ`/`STALE_STATE_HASH`; nao ha politica de retry automatico para concorrencia benignamente serializavel.

### File effects com artefatos

Eventos novos de `orchestrator.file.write` agora incluem `effects` com `path`, `before_sha256`, `after_sha256`, `bytes`, `encoding`, `artifact_sha256` e `artifact_path`.

Contagem no event store atual:

- `orchestrator.file.write` total: 108.
- Com `effects`: 74.
- Sem `effects`: 34 eventos historicos antigos.
- Artefatos em `.roadmap/artifacts/file-effects`: 101 arquivos.

Interpretação: a trilha nova e auditavel para eventos futuros, mas o historico antigo nao foi backfilled.

### Vocabulario do artigo vs core

O comando `vocabulary` apresenta `promote`, `phase.complete`, `backlog` e `ready` como historicos ou profile-specific, mapeados para o core `claim`, `complete` e `todo`. Isso reduz a aparencia de inconsistencia entre paper e core atual.

## Achados criticos e altos

### HIGH-01 - `complete + file effects` ainda nao e atomicamente seguro apos append

Prova em diretorio temporario: foi simulado erro em `commit_staged` depois de `append_transactional`. Resultado:

```json
{
  "complete_events": 1,
  "file_write_events": 1,
  "final_file_exists": false,
  "artifact_count": 1
}
```

Ou seja: o event store pode registrar `complete` e `orchestrator.file.write`, mas o arquivo final nao aparecer. Existe artifact content-addressed, mas nao ha comando operacional de recovery/reapply que varra file-write pendente e aplique o artifact. Isso quebra a promessa de efeito atomico do ponto de vista do workspace.

Impacto: alto. O event store passa a dizer que um efeito ocorreu quando o filesystem nao reflete o evento.

Recomendacao:

- Acrescentar estado de efeito: `orchestrator.file.write.prepared`, `orchestrator.file.write.applied` ou equivalente.
- Ou mover a aplicacao final para um recovery idempotente: append primeiro, depois `esaa effects apply --pending` que verifica hash e materializa artifacts.
- Testar falha em `commit_staged`, nao apenas falha no append.

### HIGH-02 - `hotfix create` aceita hotfix orfao

Prova em diretorio temporario:

```json
{
  "status": "accepted",
  "hotfix_task": "HF-ISS-NOPE",
  "issue_id": "ISS-NOPE",
  "fixes": "TASK-NOPE"
}
```

`validate_hotfix_request()` existe e tem testes unitarios, mas `create_hotfix()` chama diretamente `build_hotfix_event()` sem validar issue existente/aberta nem tarefa original existente/done. A CLI `hotfix create` portanto aceita caminho invalido.

Impacto: alto. Permite criar tarefas hotfix sem causalidade comprovada no event store.

Recomendacao:

- Chamar `validate_hotfix_request()` dentro de `create_hotfix()` e tambem no path automatico de `issue.report` antes de `build_hotfix_event()`.
- Adicionar teste E2E via CLI/servico, nao apenas teste unitario da funcao de validacao.

### HIGH-03 - `issue report` via comando mascara `done` como `review`

Prova em diretorio temporario: apos levar `T-1000` a `done`, `report_issue()` gerou evento com:

```json
{
  "issue_prior_status": "review",
  "task_id": "T-1000"
}
```

O problema esta em `src/esaa/service.py`, onde `report_issue()` usa `task["status"] if task["status"] != "done" else "review"`. Isso contradiz o schema atualizado, que permite `prior_status=done` para `issue.report`.

Impacto: alto. Evidencia forense sobre tarefa imutavel fica incorreta.

Recomendacao:

- Remover o fallback `done -> review`.
- Fazer o comando usar sempre o status real injetado/materializado.
- Adicionar teste do comando `issue report`, nao apenas `submit` com envelope manual.

### HIGH-04 - `activity clear` nao resemeia lessons basais

Prova em diretorio temporario:

```json
{
  "lessons_after_init": 3,
  "clear_status": "cleared",
  "last_event_seq_after_clear": 0,
  "lessons_after_clear": 0,
  "verify_status": "ok"
}
```

`init` agora emite `orchestrator.view.mutate` com `BASELINE_LESSONS`, mas `clear_activity()` materializa `materialize([])` e salva `lessons.json` vazio. O teste existente cobre `init` e replay limpo, mas nao cobre `activity clear`, apesar de essa exigencia estar descrita no roadmap.

Impacto: alto. Depois de clear, `dispatch-context` deixa de injetar LES-0001/2/3 e o agente perde constraints operacionais basais.

Recomendacao:

- `activity clear` deve chamar `init` controlado, ou escrever um novo evento baseline reconstruivel apos limpar.
- Adicionar teste direto de `clear_activity(force=True)` e `dispatch-context` apos clear.

### HIGH-05 - `eligible` e `run` ainda divergem para plugin adicionado apos init

Prova em diretorio temporario:

```json
{
  "eligible_ids": ["PLG-LATE-1"],
  "run_steps_executed": 0,
  "run_events_appended": 2,
  "run_verify_status": "ok"
}
```

Cenario: apos fechar as tarefas seed, foi adicionado um `roadmap.late.json`. `eligible()` listou `PLG-LATE-1`, mas `run(steps=1)` nao despachou a tarefa. O motivo e que `run()` seleciona a partir de `roadmap["tasks"]`, enquanto `eligible()` usa `tasks_with_planned_plugins()`.

Impacto: alto. A CLI apresenta uma tarefa como executavel, mas o harness automatico nao a consome.

Recomendacao:

- Em `run()`, substituir a lista de candidatos por `tasks_with_planned_plugins()`.
- Antes de claim/complete/review de uma tarefa plugin, admitir `task.create` deterministicamente.
- Adicionar E2E: plugin criado apos init -> `eligible` lista -> `run` cria task -> claim -> complete -> review.

## Achados medios

### MED-01 - Politica efetiva de review ainda nao e `agent-qa` independente

Prova em diretorio temporario com a politica atual:

```json
{
  "agent_qa_review": "rejected",
  "code": "LOCK_VIOLATION",
  "message": "actor agent-qa != lock owner agent-spec"
}
```

`runtime_policy.review_authorization_mode()` suporta `qa_role`, mas `.roadmap/RUNTIME_POLICY.yaml` nao define `review_authorization`. O default e `owner`. Alem disso, `.roadmap/agents_swarm.yaml` declara `agent-qa` com role `quality`, enquanto `resolve_role()` espera `qa` para autorizar review role-based.

Impacto: medio/alto. O contrato narrativo fala em review por `agent-qa`, mas a politica efetiva continua owner-review, salvo override explicito.

Recomendacao:

- Definir `review_authorization: qa_role` em `RUNTIME_POLICY.yaml`.
- Alinhar role de `agent-qa` para `qa`, ou mapear `quality -> qa` em `resolve_role()`.
- Atualizar testes para usar a politica real do repo, nao apenas policy injetada no teste.

### MED-02 - Auditores criticos tem falso negativo

`src/audit/critical_findings.py` retornou zero findings, mas os bugs acima foram reproduzidos. O checker atual procura marcadores estaticos como existencia de funcoes ou strings, nao comportamento E2E.

Exemplos:

- Existe `validate_hotfix_request`, mas `create_hotfix` nao a usa.
- Existe `BASELINE_LESSONS`, mas `activity clear` nao resemeia.
- Existe `_reviewer_role`, mas a politica real nao ativa `qa_role`.
- O schema aceita `done`, mas o comando `issue report` ainda grava `review`.

Recomendacao:

- Transformar os auditores criticos em smoke tests comportamentais ou invocar fixtures temporarias.
- Fazer `critical_findings.py` falhar com findings para os casos reproduzidos acima.

### MED-03 - Metricas existem, mas nao ha evidencias reais de runner/LLM no event store atual

`metrics` mostra:

```json
{
  "llm": {"dispatch_metrics_events": 0, "latency_ms_total": 0, "tokens_total": 0},
  "runner": {"events": 0, "latency_ms_total": 0, "tokens_total": 0}
}
```

O comando `runner metrics` existe e `runner.metrics` esta no vocabulario reservado, mas o event store atual nao demonstra uso operacional por Claude Code, Codex, Antigravity ou outro runner.

Recomendacao:

- Fazer o harness externo emitir `runner.metrics` apos cada invocacao real.
- Incluir `runner_kind`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `status` e `task_id`.
- Adicionar dashboard que diferencie metricas simuladas de metricas reais.

### MED-04 - Raw roadmaps plugin continuam `todo`, enquanto a projeção canonica esta `done`

Contagem atual:

```text
.roadmap/roadmap.json              done=108, in_progress=1
.roadmap/roadmap.critical-fixes.json todo=32
.roadmap/roadmap.cmm5.json          todo=15
.roadmap/roadmap.fix.json           done=24
.roadmap/roadmap.opt.json           todo=18
```

Como o event store e a fonte da verdade, isso nao e necessariamente bug de core. Mas e uma fonte de confusao para UI/extensoes que leem arquivos plugin brutos e exibem `[CONFLICT]` ou `todo` mesmo quando a projection efetiva mostra `done`.

Recomendacao:

- Documentar explicitamente que plugin roadmap e seed/plano, nao read model.
- Fazer a extensao/UI consumir projection efetiva ou mostrar badge “planned seed” vs “effective state”.

### MED-05 - Historico antigo nao possui file effect artifacts

34 eventos `orchestrator.file.write` antigos nao tem `effects`. Isso limita replay/auditoria historica antes da mudanca.

Recomendacao:

- Aceitar como baseline historico com nota de corte em seq.
- Ou criar ferramenta de backfill auditavel que gere artifacts para eventos antigos quando o conteudo ainda puder ser reconstruido.

### MED-06 - Conteudo de fechamento em lote pode inflar `done` sem garantia semantica

O event store mostra 108 tarefas `done` e `eligible_count=0`. Parte dessa execucao em lote preservou arquivos existentes ou gerou artefatos minimos. Formalmente o ESAA aceitou `claim -> complete -> review`, mas isso nao prova que cada tarefa foi implementada com profundidade equivalente ao titulo do roadmap.

Impacto: medio. O estado `done` pode estar correto protocolarmente e fraco semanticamente.

Recomendacao:

- Para tarefas de arquitetura critica, exigir checks verificaveis por teste/auditoria especifica.
- Impedir review automatico pelo mesmo actor em trilhas criticas quando a policy prometida e QA independente.
- Criar relatorio de “done sem evidencia forte” baseado em outputs, testes associados e diff real.

## Achados baixos e higiene

### LOW-01 - Arquivos `.pyc` estao rastreados/modificados

`git ls-files '*.pyc'` lista caches Python versionados em `src/esaa/__pycache__`, `src/esaa/adapters/__pycache__` e `tests/__pycache__`. Eles aparecem modificados apos execucao de testes.

Recomendacao: remover do indice e manter `__pycache__/` e `*.pyc` no `.gitignore`.

### LOW-02 - `.roadmap/artifacts/` esta untracked e agora e parte da trilha de auditoria

Os novos eventos referenciam `.roadmap/artifacts/file-effects/<sha>.json`. O diretorio existe com 101 artifacts, mas aparece como untracked no status atual.

Recomendacao: decidir politica explicita. Se artifacts sao evidencias canonicas de file effects, devem ser versionados ou arquivados em storage confiavel. Se nao forem versionados, o event store perde verificabilidade completa em outro clone.

### LOW-03 - `--dry-run` de alguns comandos reporta `status=accepted`

`hotfix create --dry-run` e `issue report --dry-run` nao mutaram o event store, mas retornaram `status=accepted`, `events_appended=3` e `last_event_seq` simulado. Isso pode confundir operadores.

Recomendacao: padronizar resposta dry-run com `status=dry_run`, `would_append_events` e `simulated_last_event_seq`.

### LOW-04 - Versoes auxiliares ainda aparecem como 0.4.0

`.roadmap/RUNTIME_POLICY.yaml` e `.roadmap/agents_swarm.yaml` usam `version`/`registry_version` 0.4.0 enquanto o contrato principal esta em 0.4.1. Pode ser aceitavel se esses artefatos tiverem ciclo proprio, mas vale documentar.

## Matriz de correcao sugerida

1. Corrigir atomicidade real de file effects com recovery/reapply idempotente.
2. Ligar `validate_hotfix_request()` ao comando `hotfix create` e ao path automatico de hotfix.
3. Remover `done -> review` em `report_issue()`.
4. Fazer `activity clear` reseed de LES-0001/2/3 por evento reconstruivel.
5. Fazer `run()` consumir `tasks_with_planned_plugins()` e admitir `task.create` antes do claim plugin.
6. Ativar `review_authorization: qa_role` e alinhar role `agent-qa`.
7. Trocar checks estaticos de `critical_findings.py` por provas comportamentais em temp dirs.
8. Emitir `runner.metrics` reais pelo harness externo.
9. Definir politica de retencao/versionamento de `.roadmap/artifacts/file-effects`.
10. Limpar `.pyc` rastreados e reforcar `.gitignore`.

## Status final da auditoria

- O core deterministicamente verifica e a suite passa.
- O sistema nao esta quebrado no fluxo feliz.
- As falhas atuais sao principalmente de recuperacao, politica efetiva e cobertura de auditoria.
- O principal insight: o ESAA ja governa bem o “evento aceito”, mas ainda precisa fechar melhor o “efeito aplicado” e a “evidencia operacional real”.

## Closure ESAA

- Task ID: QA-1817
- Summary: levantamento critico do sistema atual apos execucao completa, com provas em comandos, testes, event store e diretorios temporarios.
- Changed files: `docs/qa/ESAA-current-system-survey-after-full-run.md`.
- Tests run: `python -m pytest -q` (`146 passed`), `python -m esaa --root . verify`, auditores em `src/audit/*`.
- ESAA verification: executada pelo Orchestrator no complete/review desta tarefa.
- ESAA closure status: pending review no momento da emissao do complete; deve virar `done` apos review approve.
- Blockers, if any: nenhum para gerar o relatorio; ha achados tecnicos listados acima.
