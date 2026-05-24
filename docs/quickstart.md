# ESAA Quickstart

This quickstart starts from an empty directory after installing `esaa-core`.

## Install

```bash
python -m pip install esaa-core==0.5.0b1
```

For local development from this repository:

```powershell
$env:PYTHONPATH='src'
```

## Create A Workspace

```bash
mkdir esaa-demo
cd esaa-demo
esaa bootstrap --profile public
esaa init
esaa verify
esaa eligible
```

`bootstrap` installs governance templates. `init` creates the event store and
derived read models.

## Run One Governed Task

```bash
esaa claim T-1000 --actor agent-spec
```

Create `file-updates.json`:

```json
[
  {
    "path": "docs/spec/T-1000.md",
    "content": "# T-1000\n\nInitial public beta spec artifact.\n"
  }
]
```

Complete and review:

```bash
esaa complete T-1000 --actor agent-spec --check "artifact created" --file-updates file-updates.json
esaa review T-1000 --actor agent-qa --decision approve
esaa verify
```

## Source Of Truth

`.roadmap/activity.jsonl` is the append-only source of truth. The files
`.roadmap/roadmap.json`, `.roadmap/issues.json`, and `.roadmap/lessons.json`
are deterministic projections rebuilt by the core.
