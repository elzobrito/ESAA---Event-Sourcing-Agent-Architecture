# FIX-1809 — Unified eligible and run plugin dispatch policy

## Problema
`esaa eligible` retorna tarefas dos plugins (`roadmap.*.json`) que poderiam ser
ingeridas. Mas `esaa run` só seleciona tarefas já presentes no event store via
`select_next_task(roadmap["tasks"])`. Resultado: plugins ficam "elegíveis" mas
nunca executam via `run` — só via init com seed.

## Politica unificada

`service.run` (cada iteração):
1. Lê event store, materializa roadmap atual.
2. Computa "planned plugin tasks" via `load_plugin_seeds(root)`.
3. Combina: união de (roadmap.tasks) + (planned plugin tasks com `source=roadmap_plugin`).
4. Para cada planned plugin task NÃO presente no event store:
   - Append `task.create` event via `append_transactional` (admissão determinística).
5. Após admissão, segue fluxo normal: `select_next_task` na união.
6. Adiciona campo `source` no contexto: `event_store` (já admitida) ou
   `roadmap_plugin` (recém-admitida).

## Determinismo

- Ordem de admissão: plugins sorted por filename, depois tasks sorted por task_id.
- Re-execução é idempotente: tasks já admitidas (presentes no event store) não
  são re-criadas.

## Parallel groups

`run --parallel N` continua a usar `parallel_groups` da união planned+admitted.
Grupos preservam disjunção de `outputs.files`.

## Dependencies

`select_next_task` continua respeitando `depends_on`. Plugin task A com
dep em event-store task B só é elegível quando B está `done`.
