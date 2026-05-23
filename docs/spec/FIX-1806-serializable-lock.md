# FIX-1806 — Serializable append lock policy

## Problema
O lock atual (`activity.lock` via O_EXCL) protege a operacao de **escrita** no
arquivo `activity.jsonl`, mas NÃO protege a janela entre:
- `parse_event_store(root)` (lê estado)
- `next_event_seq(events)` (decide próximo seq)
- `materialize(events + new)` (valida)
- `append_events(root, new)` (escreve)

Dois processos paralelos podem ambos ler o mesmo estado, computar `event_seq=N`,
e ambos appendar — gerando `event_seq` duplicado ou gap.

## Politica serializable

Toda transação de append é envelopada por um **lock-then-revalidate-then-write**:

```
acquire_lock()
events = parse_event_store(root)
if expected_first_seq is not None:
    if next_event_seq(events) != expected_first_seq:
        raise STALE_STATE_ERROR
if expected_projection_hash is not None:
    if compute_hash(materialize(events)) != expected_projection_hash:
        raise STALE_STATE_ERROR
new_events = build_events_fn(events)        # decide event_seq aqui
final = materialize(events + new_events)    # valida transicao
append_events(root, new_events)             # escreve
save_projections(root, final)
release_lock()
```

## Inputs

- `expected_first_seq` (opcional): se o caller já leu o estado fora do lock e
  espera um seq específico, valida que ninguém appendou entre leitura e lock.
- `expected_projection_hash` (opcional): hash do roadmap.json esperado.

## Stale-state rejection

- `STALE_STATE_SEQ`: expected_first_seq != next_event_seq após re-parse
- `STALE_STATE_HASH`: expected_projection_hash != computed_hash após re-parse
- Caller deve re-ler estado e tentar novamente

## Invariantes

- `event_seq` monotônico sem gaps em qualquer momento
- Nenhum write em `activity.jsonl` fora do lock
- Nenhuma projeção stale: write de roadmap.json sempre coerente com o último append
- `verify_status=ok` após qualquer sequência de appends concorrentes

## API

```python
def append_transactional(
    root: Path,
    build_events_fn: Callable[[list[dict]], list[dict]],
    expected_first_seq: int | None = None,
    expected_projection_hash: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Run an atomic append transaction.

    Returns the final projection dict with last_event_seq, hash, etc.
    Raises ESAAError(STALE_STATE_SEQ / STALE_STATE_HASH / STORE_LOCK_TIMEOUT).
    """
```
