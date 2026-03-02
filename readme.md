# ESAA — Event Sourcing for Autonomous Agents

> **Treat LLMs as intention emitters under contract, not as developers with unrestricted permissions.**

ESAA is an architecture for orchestrating autonomous LLM-based agents in software engineering workflows. It applies the [Event Sourcing](https://www.elzobrito.com/esaa/) pattern to the agent lifecycle: the source of truth is an **immutable append-only event log**, not the current repository snapshot. Every intention, decision, and effect is recorded as a fact, and the current project state is **deterministically projected** from that log.

📄 **Paper:** [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering](https://arxiv.org/pdf/2602.23193)

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
┌─────────────┐   agent_result   ┌──────────────────┐  append event  ┌─────────────┐
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

- **Agents** emit structured intentions (`agent_result`, `issue.report`) — they **cannot** write files, mutate state, or append events directly.
- **Orchestrator** validates outputs against JSON Schema + boundary contracts, persists events, applies effects, and projects the read-model.
- **Event Store** (`activity.jsonl`) is the single source of truth — append-only, ordered by `event_seq`.
- **Read-Model** (`roadmap.json`) is a pure projection, verifiable by replaying the event store and comparing SHA-256 hashes.

---

## Repository Structure

```
.roadmap/
├── activity.jsonl                              # Event store (append-only, source of truth)
├── roadmap.json                                # Read-model: task state (derived, verifiable)
├── issues.json                                 # Read-model: open/resolved issues
├── lessons.json                                # Read-model: learned constraints
├── snapshots/                                  # Integrity snapshots (verify corruption recovery)
│
├── AGENT_CONTRACT.yaml                         # What agents CAN and CANNOT do
├── ORCHESTRATOR_CONTRACT.yaml                  # What the orchestrator MUST do
├── RUNTIME_POLICY.yaml                         # TTLs, retries, escalation, rollback
├── STORAGE_POLICY.yaml                         # Event store format and field constraints
├── PROJECTION_SPEC.md                          # How events → state (pure function spec)
│
├── agent_result.schema.json                    # JSON Schema: validates every agent output
├── roadmap.schema.json                         # JSON Schema: validates roadmap.json
├── issues.schema.json                          # JSON Schema: validates issues.json
├── lessons.schema.json                         # JSON Schema: validates lessons.json
│
├── agents_swarm.yaml                           # Agent registry and role resolution
│
├── PARCER_PROFILE.agent-spec.yaml              # Metaprompting profile: specification agent
├── PARCER_PROFILE.agent-impl.yaml              # Metaprompting profile: implementation agent
├── PARCER_PROFILE.agent-qa.yaml                # Metaprompting profile: quality agent
└── PARCER_PROFILE.orchestrator-runtime.yaml    # Metaprompting profile: orchestrator runtime

docs/
├── spec/                                       # Specification artifacts (boundary: agent-spec write)
│   └── {task_id}.md
└── qa/                                         # QA reports and checklists (boundary: agent-qa write)
    └── {task_id}.md

src/                                            # Implementation artifacts (boundary: agent-impl write)
└── {task_id}.*

tests/                                          # Test artifacts (boundary: agent-impl and agent-qa write)
└── test_{task_id}.*
```

---

## Canonical Artifacts

### Event Store — `activity.jsonl`

Append-only log of ordered events. Every state change in the project is traceable to an event:

```jsonl
{"schema_version":"0.4.0","event_id":"EV-00000001","event_seq":1,"ts":"2026-02-27T01:25:22Z","actor":"orchestrator","action":"run.start","payload":{"run_id":"RUN-0001","status":"initialized","master_correlation_id":"CID-ESAA-INIT","baseline_id":"B-000"}}
{"schema_version":"0.4.0","event_id":"EV-00000002","event_seq":2,"ts":"2026-02-27T01:25:22Z","actor":"orchestrator","action":"task.create","payload":{"task_id":"T-1000","task_kind":"spec","title":"Create initial ESAA spec document","depends_on":[],"outputs":{"files":["docs/spec/T-1000.md"]}}}
{"schema_version":"0.4.0","event_id":"EV-00000005","event_seq":5,"ts":"2026-02-27T01:25:22Z","actor":"orchestrator","action":"verify.start","payload":{"strict":true}}
{"schema_version":"0.4.0","event_id":"EV-00000006","event_seq":6,"ts":"2026-02-27T01:25:22Z","actor":"orchestrator","action":"verify.ok","payload":{"projection_hash_sha256":"7f32d838c797f55429b11483f163a1cdcf12cb75e335ebb96f0202b07dc26014"}}
```

### Read-Model — `roadmap.json`

Materialized view derived by pure projection. Includes tasks, dependencies, indexes, and verification metadata:

```json
{
  "meta": {
    "schema_version": "0.4.0",
    "immutable_done": true,
    "run": {
      "run_id": "RUN-0001",
      "status": "initialized",
      "last_event_seq": 6,
      "projection_hash_sha256": "7f32d838c797f55429b11483f163a1cdcf12cb75e335ebb96f0202b07dc26014",
      "verify_status": "ok"
    }
  },
  "project": { "name": "esaa-core", "audit_scope": ".roadmap/" },
  "tasks": [ ... ],
  "indexes": { "by_status": { "todo": 3 }, "by_kind": { "spec": 1, "impl": 1, "qa": 1 } }
}
```

---

## Event Vocabulary (v0.4.0)

| Event | Actor | Description |
|---|---|---|
| `run.start` | orchestrator | Initializes a run with run_id, baseline_id, and correlation metadata |
| `run.end` | orchestrator | Finalizes run: `success`, `failed`, or `halted` |
| `task.create` | orchestrator | Creates a new task in `todo` state (including hotfix tasks) |
| `hotfix.create` | orchestrator | Creates a hotfix task linked to an open issue; original `done` task is immutable |
| `claim` | agent | Transitions task `todo → in_progress`; sets `assigned_to` and `started_at` |
| `complete` | agent | Transitions task `in_progress → review`; requires `verification.checks` |
| `review` | agent | Transitions task: `approve → done` or `request_changes → in_progress` |
| `issue.report` | agent | Opens or updates an issue with `evidence` and `severity` |
| `issue.resolve` | orchestrator | Marks issue as resolved after hotfix approval |
| `output.rejected` | orchestrator | Rejected agent output (schema, boundary, or state violation) |
| `orchestrator.file.write` | orchestrator | Applied effect: authorized file write to repository |
| `orchestrator.view.mutate` | orchestrator | Applied effect: read-model update after projection |
| `verify.start` | orchestrator | Starts audit via deterministic replay + SHA-256 hash |
| `verify.ok` | orchestrator | Audit passed; registers `projection_hash_sha256` |
| `verify.fail` | orchestrator | Audit failed; registers divergence or corruption |

---

## Contracts and Policies

### Agent Contract (`AGENT_CONTRACT.yaml`)

Defines what agents **can** and **cannot** do:

| Allowed (agent actions) | Reserved (orchestrator only) |
|---|---|
| `claim` | `run.start` / `run.end` |
| `complete` | `task.create` / `hotfix.create` |
| `review` | `issue.resolve` |
| `issue.report` | `output.rejected` |
| | `orchestrator.file.write` / `orchestrator.view.mutate` |
| | `verify.start` / `verify.ok` / `verify.fail` |

**Boundaries by task kind** (enforcement: `fail_closed`, `prefix_match`):

| Kind | Read | Write | Forbidden write |
|---|---|---|---|
| `spec` | `.roadmap/**`, `docs/**` | `docs/**` | `src/**`, `tests/**`, `.roadmap/**` |
| `impl` | `.roadmap/**`, `docs/**`, `src/**`, `tests/**` | `src/**`, `tests/**` | `.roadmap/**` |
| `qa` | `.roadmap/**`, `docs/**`, `src/**`, `tests/**` | `docs/qa/**`, `tests/**` | `src/**`, `.roadmap/**` |

Hotfix tasks additionally require `scope_patch` — a path allowlist with `prefix_match` semantics that further restricts writable paths beyond the base `task_kind` boundary.

**Output contract** — every agent result must be a JSON envelope with:
- Required root key: `activity_event` (`action` + `task_id` mandatory)
- Optional root key: `file_updates` (array of `{path, content}`)
- Forbidden fields inside `activity_event`: `schema_version`, `event_id`, `event_seq`, `ts`, `actor`, `payload`, `assigned_to`, `started_at`, `completed_at`

### Orchestrator Contract (`ORCHESTRATOR_CONTRACT.yaml`)

Defines the orchestrator's invariants:

- **INV-001:** `done` is terminal. Never regress `task.status=done`. Corrections require the hotfix workflow.
- **INV-002:** No effect is persisted before complete output validation (fail-closed).
- **INV-003:** Enforce `boundaries.write` by `task_kind` with path normalization and `prefix_match`.
- **INV-004:** `event_seq` must be strictly monotonic and gap-free. `event_id` must be unique.
- **INV-005:** `is_single_writer: true` — one orchestrator instance writes to the event store at a time.
- **INV-006:** `roadmap.json` must be verifiable by deterministic replay; divergence → `verify_status=mismatch` or `corrupted`.

Reject conditions (any violation triggers `output.rejected` before persistence):
`unknown_action` · `schema_violation` · `boundary_violation` · `immutable_done_violation` · `lock_violation` · `invalid_transition`

### Runtime Policy (`RUNTIME_POLICY.yaml`)

- **Attempt TTL:** PT30M — exceeded attempts emit `output.rejected` with `error_code: ATTEMPT_TIMEOUT`
- **Max attempts per task:** 3 — limit exceeded auto-emits `issue.report` with `severity: high`
- **Cooldown between attempts:** PT2M
- **Issue escalation:** `low → log_only` · `medium → log_and_flag` · `high → block_task` · `critical → halt_pipeline`
- **On `verify_status=mismatch`:** `reproject_or_halt`
- **On `verify_status=corrupted`:** `halt_and_snapshot` (max 20 snapshots, `oldest_first` cleanup)

### Integrity Rules

- **`immutable_done`:** `done` is terminal — fixes must use the hotfix workflow, which creates a new task without touching the original
- **`verification_gate`:** `complete` on `impl` tasks requires `verification.checks` with ≥ 1 item; hotfix tasks require ≥ 2 items plus `issue_id` and `fixes`

---

## PARCER Metaprompting Profiles

PARCER (**P**ersona · **A**udience · **R**ules · **C**ontext · **E**xecution · **R**esponse) profiles are versioned, declarative documents that govern how each actor in the system is prompted. Unlike ad-hoc prompts, PARCER profiles are part of the repository's governance layer — they are versioned, auditable, and colocated with the contracts they enforce.

Each profile covers all six dimensions:

| Dimension | Purpose |
|---|---|
| **Persona** | Role definition, identity constraints, operating mode, failure default |
| **Audience** | Who consumes the output and how that calibrates precision requirements |
| **Rules** | Hard rules (rejection on violation) and soft rules (best practices) |
| **Context** | What the Orchestrator injects into the agent's window — and what it never injects |
| **Execution** | Step-by-step reasoning protocol before emitting any output |
| **Response** | Exact output format with annotated valid and invalid examples |

### Profile: `PARCER_PROFILE.agent-spec.yaml`

**Persona:** Analista de Requisitos e Arquiteto de Especificações. Transforms business intentions into precise, traceable technical contracts that serve as the inviolable boundary for the implementation phase.

**Key rules:**
- Produces `docs/spec/{task_id}.md` with mandatory structure: `## Objetivo`, `## Escopo`, `## Requisitos`, `## Critérios de Aceitação`
- Every requirement must be independently verifiable
- On ambiguity: `issue.report` — never guess intent

**Execution protocol:** 7 steps — validate preconditions → check active lessons → inspect open issues → produce spec artifact → assemble `file_updates` → assemble `activity_event` → self-validate JSON

```yaml
persona:
  role: >
    Analista de Requisitos e Arquiteto de Especificações do projeto ESAA.
    Você transforma intenções de negócio em contratos técnicos precisos,
    rastreáveis e verificáveis — que servirão de fronteira inviolável para
    a fase de implementação.
  identity_constraints:
    - "Você é um emissor de intenções, nunca um executor de efeitos."
    - "Você não escreve código. Você escreve contratos que o código deve satisfazer."
    - "Se você não tem certeza, o caminho correto é issue.report — nunca adivinhar."
```

### Profile: `PARCER_PROFILE.agent-impl.yaml`

**Persona:** Engenheiro de Implementação. Transforms approved specifications into concrete, testable, verifiable code artifacts. Every line proposed is a proposition — the Orchestrator decides whether it enters the repository.

**Key rules:**
- `complete` requires `verification.checks` with ≥ 1 item (≥ 2 for hotfix tasks)
- Hotfix mode (`is_hotfix=true`): additionally requires `issue_id`, `fixes`, and strict `scope_patch` prefix compliance
- On spec ambiguity: `issue.report`, never implement based on assumption
- `verification.checks` must be specific and reproducible — vague checks like "code works" are insufficient for the QA audit trail

**Execution protocol:** 9 steps — validate preconditions → check lessons → read and internalize spec → activate hotfix mode if applicable → produce implementation artifacts → formulate `verification.checks` → assemble `file_updates` → assemble `activity_event` → self-validate

```yaml
hotfix_mode:
  activated_when: "task.is_hotfix == true"
  additional_constraints:
    - "Mínimo 2 verification.checks obrigatórios (vs 1 para impl normal)."
    - "issue_id e fixes são obrigatórios em activity_event."
    - "scope_patch restringe seus paths ainda mais — respeite prefix_match estritamente."
```

### Profile: `PARCER_PROFILE.agent-qa.yaml`

**Persona:** Engenheiro de Qualidade e Auditor de Conformidade. The last line of defense before an implementation becomes `done` and immutable. Approval is a contract — rejection is protection for the entire project.

**Key rules:**
- `decision=approve` requires: all spec requirements covered, all acceptance criteria verified, no open issues with `severity=high/critical`, and `verification.checks` from agent-impl are specific and plausible
- `review` action requires `decision` + non-empty `tasks` array (schema-enforced)
- `request_changes.tasks` items must be actionable and traceable to a specific requirement or artifact
- Can report bugs outside the current task scope as separate `issue.report` with `severity=low/medium`

**Execution protocol:** 10 steps — validate preconditions → check lessons → check blocking issues → map spec requirements → inspect implementation artifacts → evaluate agent-impl's `verification.checks` → produce QA report → formulate decision → assemble `activity_event` → self-validate

```yaml
approval_bar: >
  Aprovação (decision=approve) requer: (a) todos os requisitos da spec cobertos,
  (b) todos os critérios de aceitação verificados, (c) nenhum issue crítico em aberto,
  (d) verification.checks do agente-impl são plausíveis e específicos.
```

### Profile: `PARCER_PROFILE.orchestrator-runtime.yaml`

**Note:** The Orchestrator is, by design, a deterministic runtime — not an LLM. This profile serves two purposes: (1) a contract document specifying exact expected behavior for any Orchestrator implementation; (2) an operational guide when the Orchestrator is implemented with LLM assistance for decision tasks (e.g., task selection, failure diagnosis). In both cases, the Orchestrator is the single writer of the event store.

**Key rules:**
- `is_single_writer: true` — no exceptions
- Validate before persisting, always — fail-closed is an invariant, not an option
- Never emit agent-reserved actions (`claim`, `complete`, `review`, `issue.report`) as the orchestrator actor
- `event_seq` must be strictly monotonic and gap-free; any violation halts immediately

**Execution protocol (pipeline):** 7 sequential deterministic steps:

```
1. parse_event_store         → strict JSONL parse; validate event_seq monotonicity
2. select_next_eligible_task → project state; find todo tasks with all depends_on done
3. dispatch_agent            → resolve agent by task_kind; inject purified context; start TTL timer
4. validate_agent_output     → 7-layer validation in order: JSON parse → schema → vocabulary →
                               state machine → boundary → immutability → verification gate
5. append_events             → persist: agent action event + orchestrator.file.write + orchestrator.view.mutate
6. project_views             → pure function project(events) → roadmap.json, issues.json, lessons.json
7. verify_projection         → SHA-256 replay; compare hash; emit verify.ok or verify.fail
```

---

## Task State Machine

```
         claim              complete          review(approve)
[todo] ─────────► [in_progress] ─────────► [review] ─────────► [done] ✗
                       ▲                       │                   (immutable)
                       └───────────────────────┘
                          review(request_changes)
```

`done` is terminal. Any attempt to act on a `done` task produces `output.rejected` with `immutable_done_violation`. Corrections require the hotfix workflow:

```
issue.report → hotfix.create (new task) → complete → review → issue.resolve
```

The original `done` task is never modified — the hotfix creates a new task in the roadmap with `is_hotfix=true`, `issue_id`, `scope_patch`, and `required_verification`.

---

## Verification — `esaa verify`

ESAA guarantees state reproducibility through deterministic replay:

```python
def esaa_verify(events, roadmap_json):
    projected = project_events(events)          # pure function — no I/O
    hash_input = {                              # excludes meta.run (avoids self-reference)
        "schema_version": projected["meta"]["schema_version"],
        "project": projected["project"],
        "tasks": projected["tasks"],
        "indexes": projected["indexes"]
    }
    canonical = json.dumps(hash_input, sort_keys=True, separators=(',', ':')) + '\n'
    computed = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    stored = roadmap_json["meta"]["run"]["projection_hash_sha256"]
    if computed == stored:
        return {"verify_status": "ok"}
    else:
        return {"verify_status": "mismatch"}
```

**Canonicalization rules:**
- JSON UTF-8, sorted keys, no spaces (`separators=(',', ':')`)
- Final LF newline
- Hash input excludes `meta.run` to avoid self-reference
- SHA-256 of canonicalized `{schema_version, project, tasks, indexes}`

**What `esaa verify` checks:**
1. Strict JSONL parse — every line is a valid JSON object
2. Monotonic `event_seq` — no gaps, no regressions
3. Unique `event_id` — no duplicates in the event store
4. Append-only integrity — event store was never edited
5. Boundary and authority compliance per event
6. Done immutability — no `done → non-done` transitions in replay
7. Read-model consistency — SHA-256 of canonical projection matches stored hash

**Status outcomes:**

| Status | Meaning | Orchestrator response |
|---|---|---|
| `ok` | Projection is consistent with event store | Continue |
| `mismatch` | Projection diverges from event store | `reproject_or_halt` |
| `corrupted` | Event store is malformed or tampered | `halt_and_snapshot` |

---

## Multi-Agent Orchestration

ESAA supports heterogeneous multi-agent orchestration via `agents_swarm.yaml`:

```yaml
resolution:
  by_task_kind:
    spec:  { agent: "agent-spec", template: "spec.core" }
    impl:  { agent: "agent-impl", template: "impl.core" }
    qa:    { agent: "agent-qa",   template: "qa.core"   }
  overrides:
    when_task_flag_is_hotfix:
      impl:  { agent: "agent-impl", template: "impl.hotfix" }
```

Agents are resolved by `task_kind`. The Orchestrator dispatches tasks and serializes all agent results at the event store append level — concurrent agents see a consistent projected state, but their results are validated and persisted sequentially.

**Tested with:** Claude Sonnet 4.6, Claude Opus 4.6, Codex GPT-5, Gemini 3 Pro.

---

## Orchestration Cycle

```
1.  parse_event_store → project current state
2.  select_next_eligible_task (depends_on all done; status=todo)
    └─ if none eligible and all done → emit run.end(success)
    └─ if deadlock detected → emit issue.report(severity=high)
3.  dispatch_agent → inject purified context (roadmap subset + spec + lessons + issues)
    └─ start TTL timer (PT30M)
4.  validate_agent_output (7-layer, fail-closed)
    ├─ on reject → emit output.rejected → increment attempt_count
    │              └─ if attempt_count >= 3 → emit issue.report(severity=high)
    └─ on accept:
5.      emit agent action event (claim | complete | review | issue.report)
6.      emit orchestrator.file.write (one per file in file_updates)
7.      emit orchestrator.view.mutate (one per updated read-model)
8.      project_views → rebuild roadmap.json, issues.json, lessons.json
9.      verify_projection → replay + SHA-256
        ├─ verify.ok  → continue to next eligible task
        └─ verify.fail → reproject_or_halt | halt_and_snapshot
10. emit run.end (success | failed | halted)
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

This repository contains the **landing page** case study in its clean state (only initialization events in the event store), allowing full pipeline reproduction from scratch. It also contains **ESAA-calc** as a fully executed reference run (48 events, `verify.ok`, finalized projection hash), useful as a "known-good" audit target and replay baseline.

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
   cat .roadmap/activity.jsonl    # Initialization events (run.start + task.create × N + verify.ok)
   cat .roadmap/roadmap.json      # All tasks in todo state; verify_status: ok
   ```

3. Run the orchestrator (conceptual — CLI in development):
   ```bash
   esaa run --run-id RUN-0001
   ```

4. Verify the final state:
   ```bash
   esaa verify --strict
   # Expected: verify_status=ok
   ```

---

## Roadmap

- [ ] **`esaa` CLI** — `esaa init / run / verify` with remote repository integration
- [ ] **Conflict detection** — strategies for concurrent file modifications by multiple agents
- [ ] **Time-travel debugging** — visual diff comparison at arbitrary event points in the log
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