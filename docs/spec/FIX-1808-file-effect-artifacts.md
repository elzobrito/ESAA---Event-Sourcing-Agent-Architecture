# FIX-1808 — File effect artifact and hash audit policy

## Forensic metadata em orchestrator.file.write

Estender o payload de `orchestrator.file.write` para incluir, por file_update:

```json
{
  "path": "docs/spec/X.md",
  "before_sha256": "<sha256 do conteudo previo, ou null se inexistente>",
  "after_sha256": "<sha256 do conteudo apos write>",
  "bytes": <int>,
  "encoding": "utf-8",
  "artifact_sha256": "<sha256 do payload completo do artifact>",
  "artifact_path": ".roadmap/artifacts/file-effects/<artifact_sha256>.json"
}
```

## Artifact content-addressed

`.roadmap/artifacts/file-effects/<sha>.json`:

```json
{
  "artifact_id": "ART-<sha>",
  "path": "docs/spec/X.md",
  "before_sha256": "...",
  "after_sha256": "...",
  "bytes": 1234,
  "encoding": "utf-8",
  "content": "<conteudo apos write — UTF-8 string>",
  "ts": "2026-05-23T..."
}
```

## Hash inputs canonicos

`artifact_sha256` é computado sobre o JSON canonicalizado (sort_keys=True,
ensure_ascii=False, separators=(",", ":")) do payload sem o próprio
`artifact_sha256` (auto-referência impossível).

## Missing-artifact behavior

Se `artifact_path` referenciado por um evento `orchestrator.file.write` não
existir no disco, `audit.critical_findings.check_artifacts(root)` flags
`ARTIFACT_MISSING`.

## Replay verification

Reaplicar todos `orchestrator.file.write` events deve reproduzir os arquivos
finais com `after_sha256` esperado.

## Retencao

Artifacts em `.roadmap/artifacts/file-effects/` são append-only. Não há cleanup
automático nesta versão.
