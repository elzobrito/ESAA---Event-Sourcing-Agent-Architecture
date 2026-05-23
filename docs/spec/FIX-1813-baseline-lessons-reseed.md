# FIX-1813 — Baseline lessons reseed policy

## Problema
Após `esaa init --force`, o event store é zerado e `lessons.json` fica vazio
(0 lessons). Sem LES-0001/2/3, o agente perde as constraints (no collapse,
file_updates com complete, prior_status obrigatório).

R1-fix já tornou lessons replayable via `orchestrator.view.mutate(lessons=...)`.
Mas init NÃO emite tal evento — a única forma de ter lessons é executar uma
trilha de promoção manualmente.

## Politica

`service.init` (após task.create events, antes de verify):
1. Append `orchestrator.view.mutate` com payload:
   ```json
   {
     "target": "lessons",
     "change": "baseline_reseed",
     "lessons": [<LES-0001>, <LES-0002>, <LES-0003>]
   }
   ```
2. Os 3 lessons baseline têm definições canônicas em `service.BASELINE_LESSONS`.

## Definicoes canonicas

| Lesson    | Title                                       | enforcement.mode |
|-----------|---------------------------------------------|------------------|
| LES-0001  | Nunca colapsar claim + complete             | `reject`         |
| LES-0002  | file_updates exige action=complete          | `reject`         |
| LES-0003  | prior_status obrigatorio e coerente         | `require_field`  |

(Definições completas em `src/esaa/baseline_lessons.py`.)

## Dispatch-context apos reset

Após init, `eligible`/`run` injetam lessons aplicáveis ao task_kind via
`dispatch.build_minimal_context` (já implementado em RF06). Como lessons agora
são reproduzidas por replay, sobrevivem a `esaa project` e `esaa replay`.

## Sem edicao manual de read model

`lessons.json` permanece read-only do ponto de vista do agente. Ninguém edita
o arquivo diretamente — ele é projetado a partir do event store.
