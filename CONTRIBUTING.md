# Contributing

Thanks for helping improve ESAA.

## Setup

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

On Linux/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Checks

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

For repo-local CLI checks during development, prefer:

```powershell
$env:PYTHONPATH='src'
python -m esaa --root . verify
```

## ESAA Governance Rules

- Do not manually edit `.roadmap/activity.jsonl`.
- Do not manually edit `.roadmap/roadmap.json`, `.roadmap/issues.json`, or `.roadmap/lessons.json`.
- Use Orchestrator/Core commands to append governed events and then run `esaa verify`.
- Keep event store semantics append-only and single-writer.
