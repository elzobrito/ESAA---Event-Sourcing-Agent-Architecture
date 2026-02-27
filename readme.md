# ESAA — Event Sourcing for Autonomous Agents

> **Treat LLMs as intention emitters under contract, not as developers with unrestricted permissions.**

ESAA is an architecture for orchestrating autonomous LLM-based agents in software engineering workflows. It applies the [Event Sourcing](https://www.elzobrito.com/esaa/) pattern to the agent lifecycle: the source of truth is an **immutable append-only event log**, not the current repository snapshot. Every intention, decision, and effect is recorded as a fact, and the current project state is **deterministically projected** from that log.

📄 **Paper:** [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering](https://arxiv.org/pdf/2602.23193) *(preprint)*

---

## Why ESAA?

LLM agents in software engineering suffer from three structural problems:

| Problem | How ESAA solves it |
|---|---|
| **No native state** — agents forget what they did | Append-only event log preserves the full decision trail |
| **Context degradation** — long prompts lose mid-context facts | Orchestrator injects a *purified view* (roadmap + relevant facts), not raw history |
| **Probabilistic ≠ deterministic** — free-text outputs break pipelines | Agents emit only validated JSON under boundary contracts |

Unlike snapshot-based frameworks (AutoGen, MetaGPT, LangGraph, CrewAI), ESAA provides **deterministic replay**, **hash-verified projections**, and **forensic traceability** out of the box.

---

## Architecture

```
┌─────────────┐   agent.result   ┌──────────────────┐  append event  ┌─────────────┐
│  LLM Agent  │ ───────────────► │   Orchestrator   │ ─────────────► │ Event Store │
│ (intention) │                  │ (deterministic)  │                │  (.jsonl)   │
└─────────────┘ ◄─────────────── └──────────────────┘                └──────┬──────┘
       ▲         output.rejected        │                                   │
       │                                │                              project
       │         ┌──────────────┐       │                                   │
       │         │   Boundary   │       │                                   ▼
       │         │  Contract    │  ┌────┴─────────┐                 ┌──────────────┐
       │         └──────────────┘  │ JSON Schema  │                 │  Read-Model  │
       │                           │  Validation  │                 │   (.json)    │
       │                           └──────────────┘                 └──────┬───────┘
       │                                                                   │
       └──────────────────── purified view ────────────────────────────────┘
```

**Core principle:** Agents propose, the Orchestrator disposes.

- **Agents** emit structured intentions (`agent.result`, `issue.report`) — they **cannot** write files, mutate state, or append events directly.
- **Orchestrator** validates outputs against JSON Schema + boundary contracts, persists events, applies effects, and projects the read-model.
- **Event Store** (`activity.jsonl`) is the single source of truth — append-only, ordered by `event_seq`.
- **Read-Model** (`roadmap.json`) is a pure projection, verifiable by replaying the event store and comparing SHA-256 hashes.

---

## Repository Structure

```
.roadmap/
├── activity.jsonl                          # Event store (append-only, source of truth)
├── roadmap.json                            # Read-model (derived, verifiable)
├── AGENT_CONTRACT.yaml                     # What agents CAN and CANNOT do
├── ORCHESTRATOR_CONTRACT.yaml              # What the orchestrator MUST do
├── RUNTIME_POLICY.yaml                     # TTLs, retries, escalation, rollback
├── STORAGE_POLICY.yaml                     # Event store format and constraints
├── PROJECTION_SPEC.md                      # How events → state (pure function)
├── agents_swarm.yaml                       # Agent registry and role resolution
├── PARCER_PROFILE.agent-docs.yaml          # Metaprompting profile for spec agents
├── PARCER_PROFILE.orchestrator-runtime.yaml # Orchestrator runtime profile
├── specs/                                  # Specification artifacts (produced by agents)
│   └── *.md
└── qa/                                     # QA reports and checklists
    └── *.md
src/                                        # Implementation artifacts
```

---

## Canonical Artifacts

### Event Store — `activity.jsonl`

Append-only log of ordered events. Every state change in the project is traceable to an event:

```jsonl
{"schema_version":"0.3.0","event_id":"EV-00000001","event_seq":1,"ts":"2026-02-21T09:43:00-03:00","actor":"orchestrator","action":"run.init","payload":{"run_id":"RUN-0001","status":"initialized"}}
{"schema_version":"0.3.0","event_id":"EV-00000002","event_seq":2,"ts":"2026-02-21T09:43:05-03:00","actor":"orchestrator","action":"attempt.create","payload":{"task_id":"T-1000","attempt_id":"A-T-1000-01"}}
{"schema_version":"0.3.0","event_id":"EV-00000003","event_seq":3,"ts":"2026-02-21T09:43:10-03:00","actor":"orchestrator","action":"orchestrator.dispatch","payload":{"task_id":"T-1000","attempt_id":"A-T-1000-01","actor":"agent-spec","template":"spec.generic"}}
```

### Read-Model — `roadmap.json`

Materialized view derived by pure projection. Includes tasks, dependencies, indexes, and verification metadata:

```json
{
  "schema_version": "0.3.0",
  "project": { "name": "example-landingpage", "audit_scope": ".roadmap/" },
  "run": {
    "run_id": "RUN-0001",
    "status": "success",
    "verify_status": "ok",
    "projection_hash_sha256": "6048ece9da6b7b2ed069dba8f1da223ba3..."
  },
  "tasks": [ ... ],
  "indexes": { "by_state": { ... }, "by_kind": { ... } }
}
```

---

## Event Vocabulary (v0.3.0)

| Event | Actor | Description |
|---|---|---|
| `run.init` | orchestrator | Initializes a run (metadata and scope) |
| `attempt.create` | orchestrator | Opens an attempt for a task and binds an agent |
| `attempt.timeout` | orchestrator | Expires an attempt (TTL exceeded) |
| `orchestrator.dispatch` | orchestrator | Triggers agent execution for an attempt |
| `agent.result` | agent | Structured intention (patch proposals), validated by schema |
| `issue.report` | agent/orchestrator | Defect/incident log; may spawn a hotfix task |
| `output.rejected` | orchestrator | Rejected output (schema, boundary, or authority violation) |
| `orchestrator.file.write` | orchestrator | Applied effect: authorized file writing |
| `orchestrator.view.mutate` | orchestrator | Applied effect: read-model update |
| `task.create` | orchestrator | Creates a new task (including hotfixes) |
| `task.update` | orchestrator | Updates task state (todo → in_progress → done) |
| `verify.start` | orchestrator | Starts audit via replay + deterministic hashing |
| `verify.ok` | orchestrator | Audit passed; registers `projection_hash_sha256` |
| `verify.fail` | orchestrator | Audit failed; registers divergence |
| `run.end` | orchestrator | Finalizes run (success/failed) |

---

## Contracts and Policies

### Agent Contract (`AGENT_CONTRACT.yaml`)

Defines what agents **can** and **cannot** do:

- ✅ `agent.result` — propose file patches (within boundaries)
- ✅ `issue.report` — report defects, risks, blockers
- ✅ `agent.heartbeat` — signal liveness
- ❌ `event.append` — write to event store
- ❌ `view.mutate` — write to roadmap.json
- ❌ `file.write` — write directly to filesystem
- ❌ `hotfix.create` — reserved to orchestrator
- ❌ `task.claim` — reserved to orchestrator
- ❌ `task.set_done` — done only via protocol

**Boundaries by task kind:**

| Kind | Writable paths |
|---|---|
| `spec` | `.roadmap/**/*.md`, `.roadmap/**/*.yaml` |
| `impl` | `src/**`, `tests/**`, `package.json`, `pyproject.toml`, `go.mod`, `go.sum` |
| `qa` | `.roadmap/**/*.md`, `.roadmap/**/*.yaml` |
| `emergency_patch` | `src/**`, `tests/**`, `.roadmap/**/*` |

### Orchestrator Contract (`ORCHESTRATOR_CONTRACT.yaml`)

Defines the orchestrator's invariants:

- **INV-001:** Never regress `task.state=done`. Corrections via `emergency.override` + supersede.
- **INV-002:** Every effect must reference valid `task_id` and `attempt_id`.
- **INV-003:** No effect persistence before complete output validation (fail-closed).
- **INV-004:** Enforce `boundaries.write` by `task_kind` with path normalization.
- **INV-005:** `event_seq` must be monotonic; `event_id` must be unique.
- **INV-006:** `roadmap.json` must be verifiable by replay; divergence → `verify_status=corrupted`.

### Runtime Policy (`RUNTIME_POLICY.yaml`)

- Attempt TTL: 30 minutes
- Max attempts per task: 3
- Issue escalation: low → log only, medium → flag, high → block task, critical → halt pipeline
- Auto-escalation after 3 repeated medium issues
- On verify corruption: halt pipeline, snapshot, require manual recovery

---

## PARCER Metaprompting Profiles

PARCER (**P**ersona, **A**udience, **R**ules, **C**ontext, **E**xecution, **R**esponse) profiles control how agents are prompted. Each profile enforces:

- **Persona:** role and operating principles
- **Rules:** deterministic flow (check task state → produce output → respect boundaries)
- **Output contract:** mandatory JSON envelope with required keys
- **Prohibitions:** actions the agent must never attempt

Example (`PARCER_PROFILE.agent-docs.yaml`):
```yaml
agent_profile:
  role: "agent-docs: Analista de Requisitos e Arquiteto de Especificações."
  principles:
    - "A especificação técnica é o contrato inviolável para a fase 'impl'."
    - "Event Store é sagrado: agentes não aplicam efeitos; apenas propõem."
    - "Fail-closed: se houver ambiguidade, emita issue.report."
```

---

## Verification — `esaa verify`

ESAA guarantees state reproducibility through deterministic replay:

```python
def esaa_verify(events, roadmap_json):
    projected = project_events(events)        # pure function
    computed = compute_projection_hash(projected)
    stored = roadmap_json["run"]["projection_hash_sha256"]
    return {"verify_status": "ok"} if computed == stored else {"verify_status": "mismatch"}
```

**Canonicalization rules:**
- JSON UTF-8, sorted keys, no spaces (`separators=(',', ':')`)
- Final LF newline
- Hash input excludes `run` metadata (avoids self-reference)
- SHA-256 of canonicalized `{schema_version, project, tasks, indexes}`

**What verify checks:**
1. Monotonic `event_seq` (no regression)
2. Append-only integrity (event store never edited)
3. Boundary and authority compliance
4. Done immutability (no `done` → non-done transitions)
5. Read-model consistency via hash comparison

---

## Multi-Agent Orchestration

ESAA supports heterogeneous multi-agent orchestration via `agents_swarm.yaml`:

```yaml
resolution:
  by_task_kind:
    spec:  { agent: "agent-spec", template: "spec.generic" }
    impl:  { agent: "agent-impl", template: "impl.generic" }
    qa:    { agent: "agent-qa",   template: "qa.generic" }
```

Agents are resolved by task kind. The orchestrator dispatches tasks and tracks agent activity through correlation IDs. Multiple agents can work **concurrently** — the event store serializes their results at the append level.

**Tested with:** Claude Sonnet 4.6, Claude Opus 4.6, Codex GPT-5, Antigravity (Gemini 3 Pro).

---

## Orchestration Cycle

```
1. select_next_eligible_task()
2. append attempt.create
3. emit orchestrator.dispatch → invoke agent
4. validate_agent_output (JSON Schema + boundaries + authority)
   ├─ on_reject → emit output.rejected → retry or block
   └─ on_accept:
       5. emit orchestrator.file.write (apply patches)
       6. emit task.update (state → done)
       7. project events → rebuild roadmap.json
       8. esaa verify (replay + hash)
9. emit run.end (success | failed | halted)
```

---
## Case Studies

The architecture has been validated in three case studies:

| Metric | Landing Page | ESAA-calc (Python GUI Calculator) | Clinic ASR |
|---|---|---|---|
| Tasks | 9 | 11 | 50 |
| Events | 49 | 48 | 86 |
| Agents | 3 (composition) | 3 (composition) | 4 (concurrent) |
| Phases | 1 pipeline | 1 pipeline | 15 (8 completed) |
| Components | 3 (spec/impl/QA) | 5 (engine, GUI, tests, config, docs) | 7 (DB, API, UI, tests, config, obs, docs) |
| `output.rejected` | 0 | 0 | 0 |
| `verify_status` | ok | ok | ok |
| Concurrent claims | No | No | Yes (6 in 1 min) |

This repository contains the **landing page** case study in its clean state (only `run.init` in the event store), allowing full pipeline reproduction from scratch.  
It also contains **ESAA-calc** as a fully executed reference run (48 events, `verify.ok`, finalized projection hash), useful as a “known-good” audit target and replay baseline.

---

## Getting Started

### Prerequisites

- Python 3.12+
- An LLM with structured output support (e.g., Claude, GPT, Gemini)

### Reproduce the Case Study

1. Clone the repository:
   ```bash
   git clone https://github.com/elzobrito/ESAA---Event-Sourcing-Agent-Architecture.git
   cd esaa-example-landingpage
   ```

2. Inspect the initial state:
   ```bash
   cat .roadmap/activity.jsonl    # Only run.init event
   cat .roadmap/roadmap.json      # All tasks in todo state
   ```

3. Run the orchestrator (conceptual — CLI in development):
   ```bash
   esaa run --run-id RUN-0001 --steps 9
   ```

4. Verify the final state:
   ```bash
   esaa verify --strict
   # Expected: verify_status=ok
   ```

---

## Roadmap

- [ ] **`esaa` CLI** — `esaa init / run / verify` with remote repository integration
- [ ] **Conflict detection** — strategies for concurrent file modifications
- [ ] **Time-travel debugging** — visual diff comparison at arbitrary event points
- [ ] **SWE-bench evaluation** — systematic evaluation on real issue benchmarks
- [ ] **Formal verification** — model checking of orchestrator invariants

---

## Citation

If you use ESAA in your research, please cite:

```bibtex
@article{santos2026esaa,
  title={ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering},
  author={Santos Filho, Elzo Brito dos},
  year={2026},
  note={Preprint}
}
```

---

## License

MIT

---

## Author

**Elzo Brito dos Santos Filho**
📧 elzo.santos@cps.sp.gov.br

