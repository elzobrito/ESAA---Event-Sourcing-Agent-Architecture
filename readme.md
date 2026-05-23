# ESAA - Event Sourcing for Autonomous Agents

ESAA is a governance architecture and event-sourced protocol for autonomous
software agents. It treats LLMs and coding tools as intention emitters under a
contract, while a deterministic Orchestrator validates, persists, projects, and
verifies state.

The local `esaa-core` runtime in this repository does not use MCP. It is a
Python CLI/runtime that operates directly over the repository's `.roadmap/`
event store and projections.

Paper: [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering](https://arxiv.org/pdf/2602.23193)

## Core Model

```text
ESAA governance/protocol
  -> Harness/runtime
    -> Orchestrator, single writer
      -> Agent, intention emitter
```

- Agents emit exactly one `activity_event` per invocation.
- The Orchestrator is the only writer of `.roadmap/activity.jsonl`.
- `.roadmap/activity.jsonl` is append-only and is the source of truth.
- `.roadmap/roadmap.json`, `.roadmap/issues.json`, and
  `.roadmap/lessons.json` are deterministic read models.
- File writes happen only after schema, workflow, boundary, and verification
  checks pass.
- `done` is terminal and immutable; fixes go through the hotfix flow.

## State Machine

```text
         claim              complete          review(approve)
[todo] ---------> [in_progress] ---------> [review] ---------> [done]
                       ^                       |
                       |                       |
                       +-----------------------+
                          review(request_changes)
```

Canonical agent actions:

- `claim`
- `complete`
- `review`
- `issue.report`

Reserved Orchestrator actions include:

- `run.start`, `run.end`
- `task.create`
- `hotfix.create`, `issue.resolve`
- `runner.metrics`
- `output.rejected`
- `orchestrator.file.write`
- `orchestrator.view.mutate`
- `verify.start`, `verify.ok`, `verify.fail`

## Repository Layout

```text
.roadmap/
  activity.jsonl                 append-only event store
  roadmap.json                   projected task read model
  issues.json                    projected issue read model
  lessons.json                   projected lessons read model
  AGENT_CONTRACT.yaml            agent boundaries and output contract
  ORCHESTRATOR_CONTRACT.yaml     workflow gates and single-writer rules
  RUNTIME_POLICY.yaml            attempts, cooldown, TTL, escalation
  agent_result.schema.json       agent output schema
  roadmap.schema.json            roadmap projection schema
  roadmap.*.json                 roadmap plugins
  snapshots/                     snapshots, archives, manifests

docs/spec/                       specification outputs
docs/qa/                         QA reports and evidence
src/esaa/                        deterministic runtime implementation
tests/                           runtime and protocol tests
```

Root `readme.md` is an explicit `spec` boundary exception because it is the
public onboarding artifact for the project. Source, test, and `.roadmap/` files
remain forbidden for `spec` tasks.

## Local CLI

From the repository root on Windows:

```cmd
set PYTHONPATH=src
python -m esaa --root . --help
```

On PowerShell:

```powershell
$env:PYTHONPATH='src'
python -m esaa --root . --help
```

Available top-level commands:

```text
init
run
submit
claim
complete
review
state
dispatch-context
reject
task
issue
hotfix
activity
process
project
verify
eligible
metrics
runner
scenario
vocabulary
snapshot
replay
```

## Deterministic Task Commands

`task create` is the public way to admit new planned work into the event store.
It emits `task.create` through the Orchestrator and validates the projected
`roadmap.json` against `.roadmap/roadmap.schema.json` before append.

```cmd
python -m esaa --root . task create README-1803 ^
  --kind spec ^
  --title "Update README" ^
  --description "Refresh public onboarding docs" ^
  --output readme.md ^
  --target docs
```

Then drive the state machine without spending LLM tokens:

```cmd
python -m esaa --root . claim README-1803 --actor agent-spec
python -m esaa --root . complete README-1803 --actor agent-spec --check "README reviewed" --file-updates updates.json
python -m esaa --root . review README-1803 --actor agent-spec --decision approve
```

`complete --file-updates` expects a JSON array:

```json
[
  {
    "path": "readme.md",
    "content": "# full file content\n"
  }
]
```

## Runner Telemetry

Native provider adapters are optional. When Claude Code, Codex, Antigravity, or
another external runner opens the project and drives `esaa-core`, the required
evidence is `runner.metrics`.

```cmd
python -m esaa --root . runner metrics ^
  --task-id README-1803 ^
  --actor agent-spec ^
  --runner-id codex-desktop ^
  --runner-kind codex ^
  --model gpt-5 ^
  --command-surface "python -m esaa claim/complete/review" ^
  --latency-ms 1250 ^
  --status success ^
  --correlation-id CID-README-1803
```

Metrics aggregate:

- latency
- input/output/total tokens when known
- runner kind
- model
- status
- error code
- workflow gate rejections
- attempt counts

Unknown provider values remain `null` or absent from numeric totals. The core
does not invent tokens or costs.

## Hotfix Workflow

Completed tasks are immutable. A defect in a `done` task is represented as a new
issue and a new hotfix task:

```text
issue.report -> hotfix.create -> claim -> complete -> review -> issue.resolve
```

Hotfix `complete` requires at least two `verification.checks`, `issue_id`, and
`fixes`. File writes must stay inside `scope_patch`.

Deterministic commands:

```cmd
python -m esaa --root . issue report T-1000 --actor agent-qa --issue-id ISS-1 --severity medium --title "Issue" --symptom "Observed problem" --repro-step "Reproduce it" --fixes T-1000
python -m esaa --root . hotfix create --issue-id ISS-1 --fixes T-1000 --scope-patch src/hotfix/
python -m esaa --root . claim HF-ISS-1 --actor agent-hotfix
python -m esaa --root . complete HF-ISS-1 --actor agent-hotfix --check unit --check regression --file-updates updates.json
python -m esaa --root . review HF-ISS-1 --actor agent-hotfix --decision approve
```

Demonstration scenario:

```cmd
python -m esaa --root . scenario hotfix
python -m esaa --root . scenario hotfix --current --issue-id ISS-DEMO
```

The default scenario uses a temporary workspace. `--current` appends real events
to the current repository.

## Parallel Dispatch And Write Conflicts

`eligible` reports executable tasks and `parallel_groups`.

```cmd
python -m esaa --root . eligible
python -m esaa --root . run --parallel 4 --until-done
```

The runtime prevents conflicting writes in concurrent waves:

- exact path conflict: `docs/spec/a.md` vs `docs/spec/a.md`
- directory-prefix conflict: `docs/spec/` vs `docs/spec/a.md`
- distinct paths remain parallelizable

If an effective write set conflicts with an already admitted write in the same
wave, the Orchestrator emits `output.rejected` with `WRITE_CONFLICT` and applies
no second file side effect.

## Snapshots And Compaction

Snapshots capture projected state and replay evidence. Staged compaction writes
a snapshot, event archive, tail file, and manifest while preserving the live
event store.

```cmd
python -m esaa --root . snapshot --before 100 --dry-run
python -m esaa --root . snapshot --before 100 --compact --dry-run
python -m esaa --root . snapshot --before 100 --compact
```

Compaction refuses unsafe states:

- missing or mismatched roadmap projection
- `verify_status != ok`
- `--before` above the last `verify.ok`
- missing archive/tail during replay checks

## Vocabulary Evolution

The paper and older profiles may mention `promote`, `phase.complete`,
`backlog`, or `ready`. In core v0.4.1 these are historical or profile-specific
terms, not active core actions.

```cmd
python -m esaa --root . vocabulary
python -m esaa --root . vocabulary --profile core-v0.4.1
```

Core v0.4.1 uses:

- statuses: `todo`, `in_progress`, `review`, `done`
- actions: `claim`, `complete`, `review`, `issue.report`

## Verification

Verify reconstructs the read models from the event store and compares the
projection hash.

```cmd
python -m esaa --root . verify
python -m esaa --root . project
python -m esaa --root . replay --no-write
```

Status meanings:

| Status | Meaning |
| --- | --- |
| `ok` | projected read model matches the event store |
| `mismatch` | stored projection diverges from replay |
| `corrupted` | event store cannot be parsed or has invalid sequence |

## Administrative Activity Command

`activity clear` is destructive and exists for deliberate resets. It always
creates a backup first.

```cmd
python -m esaa --root . activity clear --force
```

Use `--dry-run` before destructive cleanup:

```cmd
python -m esaa --root . activity clear --force --dry-run
```

## Development

Run the full test suite:

```cmd
set PYTHONPATH=src
python -m pytest -q
```

Current coverage includes:

- state machine transitions
- strict agent result validation
- deterministic CLI commands
- roadmap plugin eligibility
- external runner telemetry
- hotfix lifecycle and production trace
- parallel dispatch and write conflicts
- snapshot and staged compaction
- vocabulary mapping
- file locking for append-only writes
- schema strictness for `task create`

## Operational Rules

- Do not edit `.roadmap/activity.jsonl` manually.
- Do not edit read models by hand; reproject them from the event store.
- Do not mark tasks `done` directly; only approved review can do that.
- Do not reopen `done` tasks; use hotfix.
- Treat `PRIOR_STATUS_MISMATCH` as context lag, not task completion.
- Prefer deterministic commands when the state machine can advance without an
  LLM call.

## Citation

```bibtex
@article{santos2026esaa,
  title={ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering},
  author={Santos Filho, Elzo Brito dos},
  year={2026},
  note={Preprint}
}
```

## License

MIT

## Author

Elzo Brito dos Santos Filho

