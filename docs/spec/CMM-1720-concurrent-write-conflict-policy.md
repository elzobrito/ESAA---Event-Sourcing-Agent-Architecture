# CMM-1720 Concurrent Write Conflict Policy

## Write Sets

The planned write set comes from `outputs.files`.
The effective write set comes from `file_updates.path`.

Two write sets conflict when:

- the normalized paths are equal;
- one path is a directory prefix, marked by trailing `/`, and the other path is
  under that directory.

## Dispatch Rule

Tasks with conflicting planned write sets cannot be placed in the same
`parallel_group`.

## Admission Rule

Completes admitted in the same parallel wave are serialized through append-only
event admission. If an effective write set conflicts with a write already
admitted in the same wave, the Orchestrator emits `output.rejected` with
`WRITE_CONFLICT` and does not write the file.

## Examples

- `docs/spec/a.md` vs `docs/spec/a.md`: conflict.
- `docs/spec/` vs `docs/spec/a.md`: conflict.
- `docs/spec/a.md` vs `docs/qa/a.md`: no conflict.
- hotfix writes must also pass `scope_patch`.

