# Repository Hygiene

This repository keeps ESAA governance artifacts auditable while excluding local
runtime noise.

## Tracked

- Canonical contracts and schemas under `.roadmap/`.
- Roadmap plugins that describe planned work.
- Source, tests, documentation, and committed audit evidence.
- Content-addressed file-effect artifacts when they are part of a governed
  trace.

## Ignored

- Python bytecode and test caches.
- Coverage, packaging, and virtual environment output.
- Local editor and OS files.
- ESAA lock files, transient backups, processed inbox folders, and generated
  snapshot archives.

## Operational Rule

Never ignore `.roadmap/activity.jsonl`, canonical contracts, schemas, or roadmap
plugins. Those files are the audit surface for replay, verification, and task
eligibility.
