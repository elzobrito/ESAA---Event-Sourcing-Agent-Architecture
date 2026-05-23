# Levantamento critico do sistema ESAA atual

Data: 2026-05-23
Task: QA-1815
Modo: QA governado, com analise de contratos, schemas, harness/runtime, CLI, auditorias, testes, event store e documentacao.

## Resumo executivo

O ESAA atual esta em um estado melhor do que a versao anterior: a projecao verifica como `ok`, a suite automatizada passa, o vocabulario historico foi formalizado, `runner.metrics` existe no vocabulario/CLI, ha comandos deterministas para estado, elegibilidade, metricas, runner, snapshot, replay e hotfix, e varios modulos novos foram criados para os gaps CMM5.

Porem, o levantamento encontrou uma diferenca importante entre "capability presente" e "capability exercida pelo harness real". Varios fixes existem como modulo auxiliar, spec ou teste isolado, mas ainda nao foram conectados no caminho principal `submit` / `run` / CLI. Isso faz com que as auditorias internas retornem zero findings enquanto o comportamento real ainda apresenta gaps criticos.

Classificacao geral: o core esta funcional e testado para o fluxo basico, mas ainda nao deve ser considerado CMM5/Optimizing. O risco principal e de falsa confianca: os checks passam, mas parte das garantias prometidas pelos contratos e roadmaps ainda nao esta aplicada no dispatch real.

## Evidencias coletadas

Comandos executados com `PYTHONPATH=src`:

- `python -m esaa --root . verify`: `ok`, inicio da analise em `last_event_seq=366`, hash `5023700878223a8b4f92709e0ceef057f885897de6f19645afd7a323f27cda1a`.
- `python -m pytest -q`: `140 passed in 13.46s`.
- `python src/audit/contract_consistency.py --root .`: sem findings.
- `python src/audit/schema_conformance.py --root .`: sem findings.
- `python src/audit/eventstore_integrity.py --root .`: `366` eventos, sem findings.
- `python src/audit/traceability_and_report.py --root .`: `0` findings.
- `python src/audit/critical_findings.py --root .`: `0` findings.
- `python -m esaa --root . metrics`: `366` eventos, `33` tarefas done, `33` `orchestrator.file.write`, `0` `runner.metrics`, `0` tokens/latencia de runner.
- `python -m esaa --root . eligible`: `24` tarefas elegiveis, todas de roadmap plugins antigos.
- `python -m esaa --root . run --steps 1 --dry-run`: `steps_executed=0` apesar de `eligible_count=24`.
- `python -m esaa --root . dispatch-context AUD-1000`: contexto de tarefa plugin com `lessons: []`.
- `python -m esaa --root . hotfix create --issue-id ISS-NOPE --fixes TASK-NOPE --scope-patch src/hotfix/ --dry-run`: aceito, mesmo com issue/tarefa inexistentes.
- `python -m esaa --root . snapshot --before 100 --dry-run`: snapshot planejado com sucesso.
- `python -m esaa --root . activity clear --force --dry-run`: removeria `366` eventos, sem executar mutacao.

## Pontos fortes atuais

1. Projecao e event store estao consistentes no estado atual (`verify_status=ok`).
2. Suite automatizada ampla para o tamanho do core: 140 testes passando.
3. O CLI ja cobre o ciclo principal: `init`, `run`, `submit`, `claim`, `complete`, `review`, `state`, `dispatch-context`, `eligible`, `metrics`, `runner`, `scenario`, `snapshot`, `replay`, `activity` e hotfix.
4. `runner.metrics` foi adicionado ao vocabulario reservado e ao CLI.
5. O vocabulario historico do artigo foi mapeado para o core canonico (`promote -> claim`, `phase.complete -> complete`, `backlog/ready -> todo`).
6. Ha skeletons uteis para maturidade: `file_effects.py`, `append_transactional`, `snapshot.py`, `critical_findings.py`, cenario hotfix e testes especificos.
7. O `eligible` ja entende plugins planejados e calcula `parallel_groups`.

## Achados criticos e altos

### CRIT-01: Atomicidade de `complete + file_updates` ainda nao esta no caminho real

O modulo `src/esaa/file_effects.py` existe e tem staging/artifacts, mas `ESAAService.submit()` e `_accept_agent_output()` ainda escrevem arquivos finais diretamente antes de persistir eventos. Evidencia:

- `src/esaa/service.py:730-735`: escreve `path.write_text(item["content"])` antes do bloco de append/projecao em `772-776`.
- `src/esaa/service.py:858-863`: o fluxo de `run()` tambem escreve arquivo final diretamente.
- `rg` mostrou `stage_file_updates`, `commit_staged`, `stage_and_compute` e `write_artifact` usados apenas em testes e no modulo auxiliar, nao no harness real.

Impacto: se o processo falhar depois de escrever o arquivo e antes de append/projecao, o filesystem pode conter efeito sem evento correspondente. Isso viola a promessa central de single-writer/event-sourcing para file effects.

Recomendacao: refatorar `submit()` e `_accept_agent_output()` para usar `stage_and_compute` antes da admissao, `append_transactional` para admitir `complete + orchestrator.file.write + verify`, e `commit_staged` apenas depois do append bem-sucedido. Em falha, executar `discard_staged`.

### CRIT-02: Lock serializavel foi implementado mas nao e consumido pelo harness

`src/esaa/store.py` tem `append_transactional`, com lock, revalidacao de seq/hash e save de projections sob lock. Porem os fluxos principais continuam usando `append_events()` e `save_roadmap/save_issues/save_lessons` separados:

- `_commit_orchestrator_events()` usa `append_events()` em `src/esaa/service.py:594-598`.
- `submit()` usa `append_events()` em `src/esaa/service.py:772-776`.
- `run()` usa `append_events()` em `src/esaa/service.py:1030-1034`.

Impacto: multi-processo ainda tem janela TOCTOU entre parse, decisao, append e escrita das projections. A API transacional existe, mas e bypassada pelo caminho que importa.

Recomendacao: tornar `append_transactional` o unico caminho de append/projecao para eventos governados. `append_events()` deve virar primitiva interna ou ser restrito a bootstrap/testes.

### HIGH-03: `orchestrator.file.write` nao registra hashes/artifacts no event store real

A especificacao `FIX-1808` exige `path`, `before_sha256`, `after_sha256`, `bytes`, `encoding`, `artifact_sha256` e `artifact_path`. O event store atual tem 33 eventos `orchestrator.file.write`, todos no formato pobre `{"task_id": ..., "files": ["..."]}`. Exemplo real:

```json
{"event_seq":8,"action":"orchestrator.file.write","payload":{"task_id":"QA-1804","files":["docs/qa/ESAA-current-critical-analysis.md"]}}
```

Codigo atual:

- `src/esaa/service.py:724-725`: payload so tem lista de paths.
- `src/esaa/service.py:852-853`: mesmo problema no caminho de `run()`.

Impacto: nao ha auditoria forense suficiente para replay de file effects, deteccao de artifact ausente, hash divergente ou re-aplicacao confiavel.

Recomendacao: mudar o payload para `effects: [{path, before_sha256, after_sha256, bytes, encoding, artifact_sha256, artifact_path}]` e validar artifacts durante auditoria/replay.

### HIGH-04: `eligible` e `run` ainda divergem para roadmap plugins

`eligible` usa `tasks_with_planned_plugins()` e mostra 24 tarefas elegiveis de plugins. `run --steps 1 --dry-run` executa 0 passos. A causa esta em `src/esaa/service.py:908-915`: `run()` materializa apenas `roadmap["tasks"]` do event store e nao injeta tarefas planejadas de plugins antes de selecionar a wave.

O proprio teste `tests/test_run_consumes_plugin_tasks.py` documenta que o upgrade completo de `run` foi "deferred".

Impacto: a CLI diz que ha trabalho elegivel, mas o dispatcher autonomo nao consome esse trabalho. Isso e um bug operacional forte porque o harness nao controla a maquina de estados para plugins sem intervencao manual (`claim` direto admite plugin, mas `run` nao).

Recomendacao: em `run()`, substituir a selecao por `tasks_with_planned_plugins()` e admitir deterministicamente `task.create` antes do claim de tarefa plugin.

### HIGH-05: Lessons basais estao ausentes no estado atual e no dispatch-context

`lessons.json` esta vazio e `dispatch-context AUD-1000` retornou `lessons: []`. Isso contradiz o contrato operacional que trata LES-0001/2/3 como lessons ativas injetadas.

Evidencia adicional:

- `metrics` nao tem evento `orchestrator.view.mutate` no event store atual.
- `src/esaa/service.py:327-330` em `clear_activity()` materializa `[]` e salva lessons vazias; nao resemeia por evento.
- `tests/test_baseline_lessons_seed.py` cobre `init()`, mas nao cobre `activity clear` nem o estado real pos-clear.

Impacto: agentes nao recebem as constraints LES-0001/2/3 no contexto atual. A seguranca depende apenas de validators/gates, nao da camada de aprendizado injetada.

Recomendacao: `activity clear` deve gerar um event store minimo com `orchestrator.view.mutate baseline_reseed`, ou a documentacao deve assumir explicitamente que clear zera governance lessons e exige `init`. A melhor opcao ESAA e reseed por evento reconstruivel.

### HIGH-06: `issue.report` sobre `done` esta inconsistente entre schema, contrato e comando

O schema permite `prior_status=done` para `issue.report`, mas o contrato e o comando ainda nao estao alinhados:

- `.roadmap/agent_result.schema.json:23-27` enumera `done`.
- `.roadmap/AGENT_CONTRACT.yaml:123` ainda lista apenas `todo`, `in_progress`, `review`.
- `src/esaa/service.py:459` faz `done -> review` em `report_issue()`.

Impacto: o CLI deterministico mascara evidencia forense sobre tarefas imutaveis. Um report gerado pelo comando para uma task `done` carrega `prior_status=review`, embora o estado real seja `done`.

Recomendacao: remover o fallback `done -> review`, atualizar `AGENT_CONTRACT.yaml` para incluir `done` apenas no caso `issue.report`, e adicionar teste end-to-end do comando `esaa issue report` sobre tarefa `done`.

### HIGH-07: Validacao de hotfix existe, mas nao esta conectada ao fluxo real

`validate_hotfix_request()` existe, mas so aparece nos testes e nao e chamada por `create_hotfix()`, `build_hotfix_event()` ou `submit(issue.report)`. Dry-run real aceitou hotfix orfao:

```json
python -m esaa --root . hotfix create --issue-id ISS-NOPE --fixes TASK-NOPE --scope-patch src/hotfix/ --dry-run
```

Resultado: `status=accepted`, `task_id=HF-ISS-NOPE`.

Impacto: o Orchestrator pode criar hotfix para issue inexistente ou tarefa inexistente, quebrando rastreabilidade e a promessa de correcao governada sobre `done`.

Recomendacao: chamar `validate_hotfix_request()` antes de qualquer `hotfix.create`, tanto no comando direto quanto no caminho automatico apos `issue.report`. Rejeitar com codigo estruturado.

### HIGH-08: Politica de review independente ainda nao esta ativa no runtime padrao

A documentacao/carga inicial diz que review e de `agent-qa`, mas a politica efetiva default ainda e owner-review:

- `.roadmap/init.yaml:96-102` diz `role: "apenas agent-qa designado"`.
- `src/esaa/runtime_policy.py:122-125` usa default `review_authorization="owner"`.
- `.roadmap/RUNTIME_POLICY.yaml` nao define `review_authorization`.
- `.roadmap/agents_swarm.yaml:13-15` define `agent-qa` com role `quality`, mas `service.submit()` aceita somente `qa` ou `orchestrator` em modo `qa_role`.

Impacto: o comportamento real nao implementa a politica normativa como default. Se `qa_role` for ativado sem corrigir o swarm, `agent-qa` pode ser rejeitado por role `quality`.

Recomendacao: decidir uma unica politica canonica. Se for QA independente, definir `review_authorization: qa_role` no runtime policy e normalizar `quality -> qa` ou mudar o swarm para `role: qa`.

## Achados medios e baixos

### MED-09: Auditorias internas estao superficiais demais

`critical_findings.py` retorna zero findings, mas os gaps acima sao reproduziveis. O motivo e que os checks validam presenca de strings/funcoes, nao integracao comportamental. Exemplo: `check_serializable_append` passa se `append_transactional` existe em `store.py`, mesmo que o harness nunca a use.

Recomendacao: auditoria deve procurar chamadas efetivas e executar dry-runs comportamentais: plugin eligible vs run, hotfix orfao rejeitado, file.write com metadata, lessons injetadas, service.report_issue em done.

### MED-10: Snapshot/compactacao ainda e archive-only

`snapshot --before N --dry-run` funciona, mas `src/esaa/snapshot.py:119` define `live_event_store_rewritten: False`. A compactacao atual arquiva e escreve tail/manifest, mas nao reduz o `activity.jsonl` vivo.

Impacto: resolve auditoria/snapshot, mas nao a pressao de crescimento do event store.

Recomendacao: documentar explicitamente como "checkpoint/archive" ou implementar compactacao operacional real com manifest e replay de snapshot+tail.

### MED-11: Telemetria de runners existe, mas ainda nao ha eventos reais

`metrics` mostra `runner.events=0`, `tokens_total=0`, `latency_ms_total=0`. O comando `esaa runner metrics` existe, mas o event store atual nao demonstra uso real por Claude Code/Codex/Antigravity.

Recomendacao: integrar o harness externo para emitir `runner.metrics` apos cada invocacao, com tokens/latencia/model/status quando o runner disponibilizar esses dados.

### LOW-12: Versoes de policy/registry ainda parecem antigas

`.roadmap/RUNTIME_POLICY.yaml` declara `version: "0.4.0"` e `.roadmap/agents_swarm.yaml` declara `registry_version: "0.4.0"`, enquanto os contratos e schemas principais estao em `0.4.1`.

Impacto: baixo tecnicamente se o formato for compativel, mas ruim para onboarding e auditoria.

Recomendacao: alinhar versoes ou documentar que essas politicas seguem semver proprio.

### LOW-13: Loader de plugins varre `roadmap.schema.json`

`load_plugin_seeds()` usa glob `roadmap.*.json`, o que inclui `roadmap.schema.json`. Hoje e inofensivo porque o schema nao tem `tasks`, mas e uma fonte de ruido.

Recomendacao: excluir explicitamente `roadmap.schema.json` e qualquer arquivo de schema/backups/snapshots.

### LOW-14: Higiene de workspace/Git

O workspace esta propositalmente sujo, mas alguns itens merecem limpeza antes de commit/release:

- `src/esaa/__pycache__/*.pyc` aparece como modificado, sugerindo pyc rastreado no git.
- `opt_artifacts.py` aparece como deletado.
- Muitos docs/tests novos estao untracked.
- `.roadmap/backups` e snapshots aparecem no tree; backups devem ficar fora do versionamento operacional salvo quando forem fixtures intencionais.

Recomendacao: remover pyc do indice, confirmar destino de `opt_artifacts.py`, e revisar `.gitignore`/fixtures antes de release.

## Inconsistencias com contratos e roadmaps

1. O roadmap `roadmap.critical-fixes.json` continua com 32 tarefas `todo`, enquanto o event store projeta as mesmas 32 como `done`. O core evita duplicidade porque o event store prevalece, mas UIs que leem plugins crus vao mostrar conflito.
2. `FIX-1805`, `FIX-1806`, `FIX-1808`, `FIX-1809`, `FIX-1811` e `AUD-1814` estao marcados como done no event store, mas a implementacao entregue e parcial ou helper-only.
3. A documentacao promete lessons ativas; o estado real nao injeta nenhuma lesson.
4. A documentacao promete QA independente; o runtime default ainda e owner-review.
5. A especificacao de file effect artifacts promete metadata rica; o event store real continua path-only.

## Insights arquiteturais

O desenho ESAA esta correto em direcao: event store como verdade, read models derivados, agente emitindo intencoes e Orchestrator como autoridade. O problema atual nao e conceitual; e de fechamento operacional. O sistema criou APIs auxiliares antes de substituir o caminho antigo. Isso gera uma camada de "capabilities prontas" paralela a uma camada de "runtime real" ainda antiga.

A licao principal: para ESAA, uma feature so deve ser considerada entregue quando aparece em tres lugares ao mesmo tempo:

1. Contrato/schema/documentacao.
2. Caminho real do harness/CLI (`submit`, `run`, comandos deterministas).
3. Evento observavel no `activity.jsonl` ou teste end-to-end que prove o evento/projecao.

Hoje varias features atingem 1 e 2 parcialmente, ou 1 e testes unitarios, mas nao 3.

## Recomendacoes priorizadas

1. Refatorar `submit()` e `_accept_agent_output()` para usar `stage_and_compute`, `append_transactional` e `commit_staged`.
2. Expandir `orchestrator.file.write` para metadata rica e artifacts content-addressed no evento real.
3. Substituir `append_events()` por `append_transactional()` nos fluxos governados.
4. Fazer `run()` consumir `tasks_with_planned_plugins()` e admitir `task.create` antes de claim.
5. Corrigir `report_issue()` para preservar `prior_status=done` e alinhar `AGENT_CONTRACT.yaml`.
6. Conectar `validate_hotfix_request()` aos comandos e ao fluxo automatico de hotfix.
7. Reseed de LES-0001/2/3 apos `activity clear` por evento reconstruivel, ou renomear clear como reset sem governance.
8. Ativar e alinhar review `qa_role` se essa for a politica canonica.
9. Reescrever `critical_findings.py` para validar integracao, nao apenas presenca de strings.
10. Decidir se snapshot atual e archive/checkpoint ou compactacao real; documentar ou implementar rewrite seguro do store vivo.
11. Emitir `runner.metrics` nos harnesses externos reais.
12. Limpar Git/workspace antes de release.

## Conclusao

O ESAA atual esta estavel para o fluxo basico e evoluiu bastante em superficie de comandos e cobertura. Ainda assim, os fixes CMM5 mais importantes nao estao fechados no caminho real do harness. A prioridade deve ser integrar as APIs novas no runtime governado e elevar os testes/auditorias para end-to-end comportamental. Depois disso, os sinais de `verify ok` e `pytest passed` vao representar garantias reais, nao apenas consistencia do caminho feliz atual.