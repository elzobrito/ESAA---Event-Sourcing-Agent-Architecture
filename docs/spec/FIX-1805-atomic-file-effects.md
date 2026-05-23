# FIX-1805 — Atomic complete and file effects policy

## Problema
Hoje `service.submit(complete)` faz:
```
1. validate_agent_output
2. para cada file_update: path.write_text(content)   # ESCREVE NO DISCO
3. append_events(..., complete + file.write)         # PERSISTE EVENTOS
```

Se passo 3 falhar (lock timeout, stale seq), o passo 2 já gravou os arquivos.
Resultado: filesystem fora de sincronia com o event store.

## Politica atomica

Inverter ordem usando staging:
```
1. validate_agent_output
2. stage_file_updates(root, file_updates) -> [(final, staged, content), ...]
3. append_transactional(root, build_events_fn=lambda events: [complete, file.write])
   3a. lock
   3b. revalidate (stale check)
   3c. materialize (transicao valida?)
   3d. append events
   3e. save projections
   3f. unlock
4. commit_staged(staged)   # rename atomico para path final
5. on any error: discard_staged(staged)
```

## Recuperacao apos interrupcao

Após reinício, arquivos staged órfãos em `.roadmap/staging/` são limpos por
`file_effects.cleanup_orphan_staging(root)` — chamado em service.init e
acionável manualmente.

## Acceptance criteria

- **Append fail**: STORE_LOCK_TIMEOUT durante append não deve deixar arquivo final.
- **Stale sequence**: STALE_STATE_SEQ deve descartar staged sem aplicar.
- **Boundary violation**: detecta antes de stagear; sem efeito no disco.
- **Sucesso normal**: complete + file.write events appended; arquivos finais existem
  com mesmo content que o staged.
- **Partial write prevention**: jamais escreve em path final sem evento admitido.
