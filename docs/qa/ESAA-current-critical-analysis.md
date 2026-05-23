# Analise critica do ESAA atual

- Task ID: QA-1804
- Data: 2026-05-23
- Escopo: contratos canonicos, schemas, read models, roadmaps plugin, harness/runtime em `src/esaa`, CLI, testes e documentacao operacional.
- Modo: execucao governada ESAA (`task.create` -> `claim` -> `complete` -> `review`).

## Resumo executivo

O ESAA atual esta em um estado tecnicamente bom para um core local: a suite passou com 73 testes, `verify` esta `ok`, os read models atuais validam contra seus schemas e os roadmaps plugin tambem conformam ao schema 0.4.1. A arquitetura central esta coerente: event store append-only, projecoes deterministicas, contrato de agente estrito, comandos deterministas para claim/complete/review, telemetria de runner externo, hotfix, paralelismo, snapshot e vocabulario.

A analise critica, porem, encontrou falhas importantes que ainda impedem tratar o runtime como plenamente robusto em ambiente multi-processo ou em auditoria forense forte. As duas mais graves sao: side effects de arquivo podem acontecer antes do append do evento, e o lock multi-processo protege a escrita fisica do JSONL, mas nao protege a decisao de `event_seq` nem a transacao read-project-append. Tambem ha divergencia clara entre contrato/documentacao e runtime no papel do `agent-qa` no review: os contratos dizem que QA aprova, mas o projetor exige que o mesmo actor que fez claim faca review.

## Metodologia

Foram executadas verificacoes read-only e cenarios temporarios isolados:

- `python -m pytest -q`: 73 passed.
- `python -m esaa --root . verify`: `verify_status=ok`.
- Validacao JSON Schema de `.roadmap/roadmap.json`, `.roadmap/issues.json`, `.roadmap/lessons.json`: OK.
- Validacao dos plugins `.roadmap/roadmap.audit.json`, `.roadmap/roadmap.fix.json`, `.roadmap/roadmap.opt.json`, `.roadmap/roadmap.cmm5.json`: OK.
- `python src/audit/contract_consistency.py --root .`: sem findings.
- `python src/audit/schema_conformance.py --root .`: sem findings.
- `python src/audit/eventstore_integrity.py --root .`: sem findings.
- `python src/audit/traceability_and_report.py --root .`: sem findings.
- Reproducoes em workspaces temporarios para validar comportamento de review, plugin dispatch e atomicidade.

## Pontos fortes confirmados

1. O core local esta funcional e testado. A suite atual cobre fluxo deterministico, state machine, schema, hotfix, telemetria externa, snapshot, lock, conflito de escrita e vocabulario.
2. O schema de roadmap esta estrito e os plugins atuais conformam a ele.
3. `activity clear` cria backup e reprojeta estado vazio com `verify_status=ok`.
4. `runner.metrics` resolve bem o gap real de agentes externos: Claude Code, Codex e Antigravity podem dirigir o ESAA sem adapters nativos obrigatorios.
5. A separacao conceitual ESAA -> Harness -> Orchestrator -> Agent esta bem documentada nos documentos recentes.
6. O comando `eligible` mostra tarefas planejadas vindas de plugins sem precisar admitir `task.create`, o que e util para UI e planejamento.

## Achados criticos e altos

### F-01 Critical - Side effect de arquivo pode acontecer sem evento persistido

Evidencia estatica:

- `src/esaa/service.py` escreve `file_updates` antes de `append_events` em `submit`.
- O mesmo padrao aparece em `_accept_agent_output` usado por `run`.
- O evento `orchestrator.file.write` e preparado, mas o arquivo e escrito antes do append efetivo no event store.

Evidencia comportamental em workspace temporario:

- Foi criado um lock manual em `.roadmap/activity.jsonl.lock` antes de `complete`.
- O comando falhou com `STORE_LOCK_TIMEOUT`.
- Mesmo assim, o arquivo `docs/spec/T-1000.md` foi criado com conteudo `# written-before-append`.
- O event store ficou sem evento `complete`.

Impacto:

Isto viola a expectativa central de Event Sourcing: o efeito observavel no filesystem pode existir sem fato correspondente no log canonico. Em falha de append, queda de processo ou lock timeout, o repositorio fica em estado nao auditavel.

Recomendacao:

Introduzir uma etapa transacional de staging. O Orchestrator deve validar, preparar writes em arquivos temporarios, adquirir lock, revalidar estado e sequencia, persistir eventos, aplicar writes por rename atomico e registrar status/hash dos efeitos. Alternativamente, persistir `effect.pending` e `effect.applied` separados, mas nunca deixar arquivo final existir sem evento correlato.

### F-02 High - Lock multi-processo protege append fisico, mas nao protege `event_seq`

Evidencia estatica:

- `src/esaa/service.py` calcula `events = parse_event_store(...)` e `next_event_seq(...)` antes de chamar `append_events`.
- `src/esaa/store.py::append_events` adquire lock apenas para abrir e anexar bytes ao arquivo.
- Dentro do lock, o store nao reler o arquivo nem valida se o primeiro `event_seq` recebido ainda e o proximo esperado.

Impacto:

Dois orquestradores podem ler o mesmo ultimo evento, gerar o mesmo proximo `event_seq`, adquirir o lock em sequencia e ambos anexarem eventos com sequencia duplicada ou stale. O lock reduz intercalacao de bytes, mas nao torna a transicao read-project-append atomicamente serializavel.

Recomendacao:

Mover a secao critica para cobrir parse -> project -> validate -> assign event_seq -> append -> save projections, ou fazer `append_events` receber `expected_first_seq` e revalidar o event store dentro do lock antes de escrever. As projecoes tambem devem ser salvas sob a mesma disciplina ou por CAS/hash esperado.

### F-03 High - Event store nao registra conteudo nem hash dos file effects

Evidencia estatica:

- O evento de agente persiste apenas `activity_event`, nao o `file_updates` completo.
- `orchestrator.file.write` grava apenas lista de paths, nao conteudo, patch, tamanho, hash anterior ou hash posterior.

Impacto:

O event store consegue reconstruir estados de tarefa, mas nao consegue reconstruir ou provar integralmente os efeitos de arquivo. Isso enfraquece a promessa de replay forense: o log diz que um arquivo foi escrito, mas nao prova o que foi escrito.

Recomendacao:

Adicionar ao evento de efeito ao menos `sha256_before`, `sha256_after`, `bytes`, `encoding`, `mode` e talvez `content_ref`/artifact id. Para reproducibilidade total, armazenar patch ou conteudo canonicalizado em artifact store enderecado por hash.

### F-04 High - Review por `agent-qa` esta em conflito com o lock real

Evidencia documental:

- `.claude/CLAUDE.md` e `AGENTS.md` dizem que review e apenas do `agent-qa`.
- `ORCHESTRATOR_CONTRACT.yaml` define WG-004 como lock de quem completa, nao de quem revisa.
- `readme.md` mostra exemplos com `review --actor agent-qa`.

Evidencia de runtime:

- Em workspace temporario, `claim` e `complete` foram feitos por `agent-spec`.
- `review --actor agent-qa --decision approve` retornou `LOCK_VIOLATION`: `actor agent-qa != lock owner agent-spec`.
- `review --actor agent-spec --decision approve` foi aceito e moveu a tarefa para `done`.

Impacto:

O runtime atual nao implementa revisao independente por QA. Ele implementa auto-review pelo mesmo owner. Isso e uma divergencia importante de governanca, porque remove a separacao de funcoes prometida pelo protocolo.

Recomendacao:

Separar lock de completion e autorizacao de review. `complete` deve exigir `assigned_to == actor`; `review` deve exigir perfil/role QA ou policy explicita. Se o desenho desejado for auto-review, atualizar contratos, README, CLAUDE e AGENTS para remover a promessa de agent-qa.

## Achados medios

### F-05 Medium - `run` nao consome as mesmas tarefas plugin que `eligible` exibe

Evidencia:

- `eligible` usa `tasks_with_planned_plugins` e lista tarefas de `roadmap.*.json` como `source=roadmap_plugin`.
- `run` usa apenas `materialize(events + new_events)` e nao une as tarefas planejadas de plugins.
- Reproducao temporaria: `eligible` listou `A-000` como plugin elegivel, mas `run --steps 1` reivindicou `T-1000`, uma tarefa do event store, nao `A-000`.

Impacto:

A UI/operador pode ver uma tarefa elegivel, mas `run` nao a despacha. Para o objetivo de o harness controlar a maquina sem gastar tokens, isso cria uma diferenca perigosa entre planejamento e execucao.

Recomendacao:

Fazer `run` consumir a mesma visao de elegibilidade de `eligible`, admitindo `task.create` para tarefas plugin no inicio da wave, ou documentar que plugins precisam passar por `claim`/admissao explicita antes de `run`.

### F-06 Medium - `prior_status=done` nao e representavel, e o comando mascara como `review`

Evidencia:

- `agent_result.schema.json` limita `prior_status` a `todo`, `in_progress`, `review`.
- Contratos dizem que uma invocacao sobre tarefa `done` deve emitir `issue.report` preservando a imutabilidade violada.
- `service.report_issue` usa `prior_status = task.status if status != done else review`.

Impacto:

Um `issue.report` sobre tarefa `done` nao registra o status real no payload. Isso reduz precisao forense e contradiz a regra textual de que `prior_status` reflete o status injetado.

Recomendacao:

Incluir `done` no enum de `prior_status` para `issue.report`, ou adicionar campo separado como `observed_task_status`. Evitar registrar `review` quando o estado real era `done`.

### F-07 Medium - `hotfix create` aceita issue inexistente em dry-run e por desenho nao valida origem

Evidencia:

- `python -m esaa --root . hotfix create --issue-id ISS-NONEXISTENT --fixes T-NOPE --scope-patch src/hotfix/ --dry-run` retornou `status=accepted`.
- `build_hotfix_event` exige apenas `issue_id` e `fixes`; nao valida se existe `issue.report` aberto nem se `fixes` referencia tarefa real/done.

Impacto:

O fluxo documentado e `issue.report -> hotfix.create`, mas o comando permite criar hotfix orfao. Isso pode poluir o roadmap com hotfix sem issue real e enfraquecer rastreabilidade.

Recomendacao:

Validar que `issue_id` existe e esta `open`, que `fixes` referencia tarefa existente, e que a tarefa original esta `done` quando o hotfix representa correcao de imutabilidade.

### F-08 Medium - `runner.metrics` existe no core, mas nao esta no vocabulario reservado dos contratos canonicos

Evidencia:

- `src/esaa/constants.py` inclui `runner.metrics` em `CANONICAL_ACTIONS`.
- `readme.md` documenta `runner.metrics`.
- `.roadmap/AGENT_CONTRACT.yaml` e `.roadmap/ORCHESTRATOR_CONTRACT.yaml` nao listam `runner.metrics` em `reserved_orchestrator_actions`.
- `AGENTS.md` tambem nao lista `runner.metrics` no vocabulario reservado.

Impacto:

A feature esta implementada, mas a autoridade normativa ainda nao reconhece formalmente a action. Isso cria drift entre core e contrato.

Recomendacao:

Adicionar `runner.metrics` aos contratos canonicos e documentos operacionais, com schema/payload minimo ou referencia a `runner_metrics.py`.

### F-09 Medium - `activity clear` remove lessons ativas e nao resemeia LES-0001/2/3

Evidencia:

- Apos `activity clear`, `.roadmap/lessons.json` ficou com `lessons: []`.
- CLAUDE/AGENTS descrevem LES-0001, LES-0002 e LES-0003 como lessons ativas atuais.
- A injecao de lessons no `dispatch-context` da tarefa QA retornou `lessons: []`.

Impacto:

Os gates ainda protegem parte das regras, mas o mecanismo de aprendizado/injecao fica vazio depois de reset. Isso contradiz a expectativa operacional de lessons ativas atuais.

Recomendacao:

Decidir se lessons basais sao eventos seed, contrato estatico ou read model derivado. Se forem obrigatorias, `init`/`activity clear` deve resemea-las por evento reconstruivel ou a documentacao deve parar de chama-las de ativas quando o log foi limpo.

## Achados baixos e oportunidades

### F-10 Low - Checkers de auditoria estao verdes, mas estreitos

Os scripts em `src/audit` nao encontraram findings, mas tambem nao detectam os drifts acima: review role, `runner.metrics` fora dos contratos, side effects antes do append, hotfix orfao e divergencia `eligible` vs `run`.

Recomendacao: transformar os achados deste relatorio em checks automatizados.

### F-11 Low - `task create` permite outputs fora da boundary do kind

O schema valida forma, mas nao valida se `outputs.files` combina com `task_kind`. Isso permite criar uma tarefa `qa` planejada para escrever `src/**`, que so falharia no `complete`.

Recomendacao: validar planned write set no `task create` para falhar cedo.

### F-12 Low - Snapshots sao seguros, mas o termo compactacao pode confundir

`compact_event_store` escreve snapshot/archive/tail/manifest e declara `live_event_store_rewritten=false`. Isso e seguro, mas o nome `compact` pode sugerir que o live event store foi realmente compactado.

Recomendacao: manter o modo atual como `snapshot --archive` ou documentar explicitamente que compactacao operacional ainda e staged/archive-only.

## Inconsistencias documentais especificas

- `readme.md` mostra `review --actor agent-qa`, mas o runtime exige o owner atual da tarefa.
- `.claude/CLAUDE.md` e `AGENTS.md` descrevem review apenas por `agent-qa`; testes e `scenarios.py` usam o mesmo actor que fez claim/complete.
- Contratos e AGENTS nao listam `runner.metrics`; core e README listam.
- O texto normativo diz que `prior_status` reflete exatamente o status injetado, mas `done` nao esta no enum e o comando usa `review` como substituto.

## Insights arquiteturais

1. O core ja passou do ponto de ser apenas harness experimental. Ele tem semantica de orchestrator suficiente para exigir garantias transacionais mais fortes.
2. A decisao de tratar agentes externos como runners e registrar `runner.metrics` e correta. O gap real nao e adapter nativo, mas evidencia operacional confiavel.
3. O principal risco remanescente e a distancia entre auditabilidade de estado de tarefa e auditabilidade de efeitos de arquivo. Hoje a primeira e boa; a segunda ainda e fraca.
4. O modelo de plugins esta bom para planejamento e UI, mas precisa de uma unica fonte operacional para elegibilidade e dispatch.
5. A separacao de papeis QA precisa ser decidida: auto-review e mais simples; QA independente e mais forte. O contrato promete a segunda, o runtime implementa a primeira.

## Proximas tarefas sugeridas

1. `FIX-1805` - Transacao atomica de complete/file effects: staging, lock de secao critica e evento de efeito com hash.
2. `FIX-1806` - Lock serializavel: revalidar event_seq e projection hash dentro do lock antes de append.
3. `FIX-1807` - Review role policy: implementar `agent-qa` independente ou alinhar contratos para owner-review.
4. `FIX-1808` - Persistir hashes/conteudo referenciado de `file_updates` em `orchestrator.file.write`.
5. `FIX-1809` - Unificar `eligible` e `run` para tarefas de roadmap plugin.
6. `FIX-1810` - Corrigir `prior_status` para `issue.report` sobre `done`.
7. `FIX-1811` - Validar `hotfix.create` contra issue aberto e tarefa original existente/done.
8. `FIX-1812` - Atualizar contratos para incluir `runner.metrics` como action reservada.
9. `FIX-1813` - Reseed/replay de lessons basais apos init/clear ou alterar documentacao normativa.
10. `AUD-1814` - Expandir scripts de auditoria para cobrir os achados deste relatorio.

## Veredito

O ESAA atual esta consistente no nivel de schemas, testes unitarios e fluxo deterministico basico. Para uso local controlado, esta operacional. Para CMM 5 robusto, os proximos passos nao sao novos comandos de superficie, mas garantias de atomicidade, serializacao multi-processo, independencia de QA e evidencia forense dos efeitos de arquivo.