# File Effect Artifact Retention Policy

Every governed file effect must retain enough evidence to be audited or
recovered after append.

`orchestrator.file.write` effects must include path, before/after SHA-256,
encoding, byte count, artifact hash, and artifact path. The artifact is
content-addressed under `.roadmap/artifacts/file-effects/<sha256>.json`.

Recovery tooling must verify the artifact hash before applying content and must
be idempotent when the final file already matches the recorded after hash.
