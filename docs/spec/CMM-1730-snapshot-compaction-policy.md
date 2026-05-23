# CMM-1730 Snapshot Compaction Policy

## Snapshot Content

Each checkpoint stores:

- `roadmap`
- `issues`
- `lessons`
- `before_event_seq`
- included event count
- projection hash
- snapshot hash
- creation timestamp

## Safety Rules

- dry-run must be available before writing artifacts.
- compaction refuses when the stored projection is not `verify_status=ok`.
- `before` cannot exceed the last admitted `verify.ok`.
- compacted events are archived before any operational tail artifact is written.
- the live event store is not rewritten by the safe staged compaction mode.

## Replay Evidence

The manifest stores archive and tail paths. Replay from archive plus tail must
produce the same projection hash as the full event store replay.

## Retention

Snapshots and archives are audit artifacts. Retention may delete old checkpoints
only when an archive, manifest, and newer verified snapshot remain available.

