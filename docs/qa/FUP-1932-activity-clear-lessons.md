# FUP-1932 QA

Evidence:

- `tests/test_activity_clear_lessons_reseed.py`
- `tests/test_deterministic_cli_commands.py`

Result: `activity clear --force` reseeds LES-0001, LES-0002, and LES-0003 by
replayable events and keeps verification ok.
