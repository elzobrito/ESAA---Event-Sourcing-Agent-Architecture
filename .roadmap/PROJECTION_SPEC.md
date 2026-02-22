<!-- .roadmap/PROJECTION_SPEC.md -->
# ESAA v0.3.0 — Projection + Verify (CANÔNICO)

Fonte de verdade: `.roadmap/activity.jsonl` (append-only).  
Read-model materializado: `.roadmap/roadmap.json` (derivado e verificável).

## Enum canônico

- roadmap.run.verify_status ∈ { unknown, ok, mismatch, corrupted }
- roadmap.run.status ∈ { idle, initialized, running, success, failed, halted }

## Ordem

Eventos são aplicados estritamente por `event_seq` crescente (append index). `ts` não ordena.

## Projeção (função pura)

`project(events) -> roadmap_state`

Regras essenciais:

1. `task.create` cria task com `state=todo`.
2. `attempt.create`:
   - pre: task existe, task.state != done, task.superseded_by == null
   - eff: cria attempt(active), seta current_attempt_id, task.state=in_progress
3. `orchestrator.dispatch`:
   - pre: attempt_id == current_attempt_id e attempt.status == active
   - eff: registra metadados no attempt
4. `issue.report`:
   - eff: adiciona issue_open; aplicar efeitos conforme `.roadmap/RUNTIME_POLICY.yaml` (block/halt/etc.)
5. `attempt.timeout`:
   - pre: attempt.status == active
   - eff: attempt.status=timed_out; current_attempt_id=null; task.state=todo (ou blocked por policy)
6. `task.update` para `state=done`:
   - pre: task.state != done; attempt atual existe e está active; gating de risco/QA conforme policy
   - eff: task.state=done; attempt.status=completed; done_ts set; current_attempt_id=null
7. `emergency.override`:
   - nunca muda task done anterior para não-done
   - marca relação de supersedência no read-model (done continua done; agora “superseded”)
   - cria (por eventos) uma nova task com kind=emergency_patch

## Verify (replay + hash)
`esaa verify` faz replay completo dos eventos e valida:

1. Monotonicidade de `event_seq` (sem regressão).
2. Append-only (`activity.jsonl` nunca é editado; apenas acrescido).
3. Boundaries e autoridade (agente não pode aplicar efeitos).
4. Imutabilidade de tarefas `done` (sem regressão).
5. Consistência do read-model via comparação de hash.

### Hash de projeção (evita auto-referência)
Para evitar auto-referência (o hash dentro do próprio objeto hasheado), o ESAA define um objeto de hashing **derivado** do estado projetado:

`hash_input = {schema_version, project, tasks, indexes}`

Ou seja: o objeto `run` (metadados de execução, timestamps e `projection_hash_sha256`) **não participa** do cálculo do hash.

Canonicalização (determinística):
- JSON UTF-8
- chaves ordenadas (`sort_keys=true`)
- sem espaços (`separators=(',', ':')`)
- newline final LF (`
`)
- timezone lógica do projeto apenas para campos `ts` (não afeta canonicalização do JSON)

### Eventos de verificação (recomendado para auditoria)
O orquestrador SHOULD emitir eventos explícitos de verificação:

- `verify.start`: inicia o replay/validação (inclui flags como `strict=true`).
- `verify.ok`: registra `projection_hash_sha256` calculado e marca `run.verify_status="ok"`.
- `verify.fail`: registra divergência (`expected` vs `computed`) e marca `run.verify_status="mismatch"` ou `"corrupted"`.

Observação: por ser uma auditoria, `verify.*` pode ocorrer **antes** de `run.end` (pipeline inline) ou **após** `run.end` (auditoria pós-run). Em ambos os casos, a projeção é determinística: o último evento `verify.*` vence para `run.verify_status`.
