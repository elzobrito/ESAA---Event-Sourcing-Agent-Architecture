# CMM-1742 Protocol Vocabulary Evolution QA

## Command

```text
python -m pytest tests/test_vocabulary_evolution.py -q
python -m esaa --root . vocabulary
```

## Coverage

- `paper-v0.3`, `clinic-asr`, and `core-v0.4.1` appear in the table;
- `promote` and `phase.complete` are historical, not canonical core actions;
- `backlog` and `ready` are mapped or profile-specific;
- `claim`, `complete`, `review`, and `done` remain canonical for v0.4.1;
- the vocabulary command is read-only and does not mutate `activity.jsonl`.

## Recommendation

Use the mapping table in papers, READMEs, and contracts to frame old terms as
history or profile alternatives.

