# FIX-1811 — Hotfix create validation policy

## Problema
`service.build_hotfix_event(events, issue_payload)` atualmente verifica:
- `issue_id` e `fixes` presentes
- Não cria duplicata para mesmo HF-<id>

Mas NÃO verifica:
- Issue existe e está aberta
- `fixes` aponta para task existente
- Para hotfix de done immutable, target deve estar done
- `scope_patch` não vazio

## Validacoes adicionadas

| Check                                          | Reject code             |
|------------------------------------------------|-------------------------|
| issue_id refere issue inexistente              | `HOTFIX_ISSUE_NOT_FOUND` |
| issue existe mas status != "open"              | `HOTFIX_ISSUE_NOT_OPEN`  |
| fixes aponta para task_id inexistente          | `HOTFIX_TARGET_NOT_FOUND`|
| fixes target não está `done` (para imm-done)   | `HOTFIX_TARGET_NOT_DONE` |
| scope_patch vazio ou ausente                   | `HOTFIX_SCOPE_INVALID`   |
| Duplicate HF-<issue_id>                        | (silent, retorna None)   |

## Fluxo preservado

`issue.report → hotfix.create → claim → complete(≥2 checks) → review → issue.resolve`
continua válido quando todas as validações passam.

## Implementação

Em `service.build_hotfix_event`:
```python
def build_hotfix_event(current_events, issue_payload, ...):
    issue_id = ...
    fixes = ...
    # 1. valida issue_id existe e está open
    open_issues = {iid for iid, st in current_open_issues(current_events).items()}
    if issue_id not in open_issues:
        raise ESAAError("HOTFIX_ISSUE_NOT_FOUND" or "HOTFIX_ISSUE_NOT_OPEN", ...)
    # 2. valida fixes target
    tasks = {t["task_id"]: t for t in current_tasks(current_events)}
    if fixes not in tasks:
        raise ESAAError("HOTFIX_TARGET_NOT_FOUND", ...)
    # 3. valida done se imutável
    if tasks[fixes].get("immutability", {}).get("done_is_immutable"):
        if tasks[fixes]["status"] != "done":
            raise ESAAError("HOTFIX_TARGET_NOT_DONE", ...)
    # 4. valida scope_patch
    scope_patch = issue_payload.get("scope_patch") or []
    if not scope_patch:
        raise ESAAError("HOTFIX_SCOPE_INVALID", ...)
    # 5. continua fluxo existente
```
