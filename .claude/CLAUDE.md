# CLAUDE.md — Contrato operacional ESAA

> Versão operacional curta para runners. Em divergência, os artefatos canônicos em `.roadmap/` prevalecem.
> O ESAA não usa MCP. Use a CLI ESAA: `python -m esaa`.

## 1. Autoridade

ESAA é o protocolo de governança. Harness executa. Orchestrator é o single writer do event store. Agente emite intenções válidas, nunca escreve diretamente no store.

Fontes canônicas:
- `.roadmap/activity.jsonl` é a verdade histórica.
- `.roadmap/roadmap.json`, `.roadmap/issues.json`, `.roadmap/lessons.json` são projeções.
- `.roadmap/AGENT_CONTRACT.yaml`, `.roadmap/ORCHESTRATOR_CONTRACT.yaml`, `.roadmap/agent_result.schema.json`, `.roadmap/RUNTIME_POLICY.yaml` definem contrato e runtime.

Não edite manualmente event store nem read models.

## 2. CLI e identidade de runner

O pacote público é `esaa-core`, mas o módulo/comando é `esaa`.

```powershell
python -m esaa --version
python -m esaa --root . verify
python -m esaa --root . eligible
python -m esaa --root . roadmap status --detail
```

Todo comando que escreve no event store deve identificar runner:

```powershell
python -m esaa --root . --runner claude-code submit --actor agent-spec output.json
# ou:
$env:ESAA_RUNNER_ID = "claude-code"
```

Regras:
- Use `--runner <id>` ou `ESAA_RUNNER_ID` em `submit`, `task create`, `init`, `run`.
- O agente nunca envia campo `runner`; o Orchestrator carimba.
- Runners conhecidos: `claude-cowork`, `claude-code`, `codex`, `human-terminal`, `unattended`.
- Em validação strict, runner fora do registro falha com `RUNNER_UNKNOWN`.

## 3. Concorrência

Até locks robustos estarem validados no workspace alvo:
- Um runner por vez neste workspace.
- Se `.roadmap/activity.jsonl.lock` existir antes de escrever, pare e pergunte.
- Se encontrar `STORE_LOCK_TIMEOUT`, `JSONL_INVALID` ou `EVENT_SEQ_*`, pare e reporte.
- Após escrita governada, rode `python -m esaa --root . verify`.
- Não reivindique tarefa atribuída a outro runner.

## 4. Modos

### Read-only

Use para análise, diagnóstico, explicação ou inspeção. Não emita `claim`, `complete`, `review`, nem `file_updates`.

Fechamento:

```text
- Task ID: N/A
- Summary: <o que foi feito>
- Changed files: Nenhum.
- Tests run: Nenhum.
- ESAA verification: Not run.
- ESAA closure status: Not applicable — read-only request.
- Blockers, if any: <se houver>
```

### Execução governada

Use quando o usuário pede implementar/corrigir/gerar artefatos sob ESAA.

Regras:
- Two-step obrigatório: `claim` em uma invocação, `complete` em outra.
- Exatamente uma `activity_event` por output.
- JSON puro, sem markdown e sem texto fora do envelope.
- `prior_status` sempre presente e coerente.
- `file_updates` apenas com `action=complete`.
- O agente não aplica efeitos finais diretamente; envia `file_updates`.
- `done` é imutável; problemas viram `issue.report`.

## 5. Decision tree

1. `task_status == todo` -> `claim`.
2. `task_status == in_progress` e `assigned_to` é seu actor -> executar e `complete`.
3. `task_status == review` -> `review` apenas por `agent-qa`.
4. `task_status == done` -> `issue.report`.
5. Lesson ativa inviabiliza o output -> `issue.report`.
6. Dependência ausente, boundary impossível, contexto insuficiente ou lock divergente -> `issue.report`.

## 6. Envelopes canônicos

### claim

```json
{
  "activity_event": {
    "action": "claim",
    "task_id": "T-000",
    "prior_status": "todo"
  }
}
```

### complete com conteúdo completo

```json
{
  "activity_event": {
    "action": "complete",
    "task_id": "T-000",
    "prior_status": "in_progress",
    "notes": "Resumo objetivo.",
    "verification": {
      "checks": ["teste ou inspeção executada"]
    }
  },
  "file_updates": [
    {
      "path": "docs/spec/T-000.md",
      "content": "# Conteúdo completo\n"
    }
  ]
}
```

### complete com edits

```json
{
  "activity_event": {
    "action": "complete",
    "task_id": "T-000",
    "prior_status": "in_progress",
    "verification": {
      "checks": ["edição validada"]
    }
  },
  "file_updates": [
    {
      "path": "src/esaa/service.py",
      "base_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "edits": [
        {
          "old_string": "texto antigo exato",
          "new_string": "texto novo",
          "replace_all": false
        }
      ]
    }
  ]
}
```

Semântica de edits:
- O Orchestrator resolve `{path, base_sha256, edits}` para `{path, content}` antes de external effects, resource limits, staging e artifacts.
- `base_sha256` é sha256 dos bytes atuais do arquivo.
- `old_string` deve casar no texto progressivamente editado.
- `old_string` casa contra o texto UTF-8 decodificado com os newlines exatos do arquivo (CRLF incluído — não normalize `\r\n` para `\n`); arquivo não-UTF-8 → `EDIT_INVALID`.
- Mais de um match exige `replace_all=true`.
- Códigos: `EDIT_BASE_MISMATCH`, `EDIT_TARGET_NOT_FOUND`, `EDIT_AMBIGUOUS`, `EDIT_INVALID`.

### review

```json
{
  "activity_event": {
    "action": "review",
    "task_id": "T-000",
    "prior_status": "review",
    "decision": "approve",
    "tasks": ["T-000"]
  }
}
```

### issue.report

```json
{
  "activity_event": {
    "action": "issue.report",
    "task_id": "T-000",
    "prior_status": "in_progress",
    "issue_id": "ISS-0000",
    "severity": "high",
    "title": "Título objetivo",
    "evidence": {
      "symptom": "o que falhou",
      "repro_steps": ["passo reproduzível"]
    }
  }
}
```

## 7. Workflow gates

| Gate | Regra | Reject |
|---|---|---|
| WG-001 | `complete`/`review` exigem claim prévio | `MISSING_CLAIM` |
| WG-002 | `complete` exige verification; `file_updates` só com complete | `MISSING_VERIFICATION` / `MISSING_COMPLETE` |
| WG-003 | `prior_status` bate com status real | `PRIOR_STATUS_MISMATCH` |
| WG-004 | quem completa é quem reivindicou | `LOCK_VIOLATION` |
| WG-005 | exatamente uma action por output | `ACTION_COLLAPSE` |

Mínimos de `verification.checks`: `spec=1`, `impl=1`, `qa=1`, `hotfix=2`.

## 8. Lessons

Trate cada lesson com `enforcement.mode` em {`reject`, `require_field`, `require_step`} como **constraint inviolável**. `warn` não bloqueia por si só, mas deve ser respeitado.

Baseline:
- LES-0001: nunca colapsar `claim` + `complete`.
- LES-0002: `file_updates` sem `action=complete` é inválido.
- LES-0003: `prior_status` é obrigatório e coerente.

## 9. Done, hotfix e tentativas

`done` é terminal. Nunca reabra, edite ou emita `claim`/`complete`/`review` sobre task done. Problema em task done -> `issue.report`; hotfix é nova tarefa criada pelo Orchestrator.

Policy padrão: 3 tentativas por tarefa, cooldown de 2 minutos, TTL de 30 minutos. `PRIOR_STATUS_MISMATCH` não consome attempt.

## 10. Regra final

Uma action por invocação. `prior_status` sempre. `file_updates` só com `complete`. JSON puro. O agente não escreve no event store nem em read models. Na dúvida, `issue.report` com evidência.
