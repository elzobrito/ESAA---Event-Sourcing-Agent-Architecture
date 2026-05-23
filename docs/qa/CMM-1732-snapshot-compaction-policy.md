# CMM-1732 Snapshot Compaction QA

## Command

```text
python -m pytest tests/test_snapshot_compaction.py -q
python -m esaa --root . snapshot --before <seq> --dry-run
python -m esaa --root . snapshot --before <seq> --compact --dry-run
```

## Coverage

- snapshot dry-run writes no files;
- staged compaction writes snapshot, archive, tail, and manifest;
- compaction refuses non-ok projections;
- replay from archive plus tail matches the full projection hash;
- the live event store is preserved in the safe staged mode.

## Known Limit

This implementation stages compaction artifacts and does not rewrite the live
event store by default. That keeps audit recovery simple while preserving a
path to future snapshot-aware live replay.

