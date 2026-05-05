# AGENTS.md

## Purpose

This repository uses ESAA: Event Sourcing for Autonomous Agents.

ESAA is the execution protocol for agent work in this repository. It is not optional process documentation.

Code changes are not task completion. A task is complete only when the ESAA closure rules for the current execution mode are satisfied.

This file is the short operational guide for agents such as Codex. The canonical ESAA state remains inside `.roadmap/`.

---

## Canonical ESAA Sources

The canonical source of truth is:

- `.roadmap/activity.jsonl`

Roadmap files are projections/read models derived from the event log. They are not the primary source of truth.

Common ESAA artifacts may include:

- `.roadmap/init.yaml`
- `.roadmap/activity.jsonl`
- `.roadmap/roadmap.json`
- `.roadmap/issues.json`
- `.roadmap/lessons.json`
- `.roadmap/AGENT_CONTRACT.yaml`
- `.roadmap/RUNTIME_POLICY.yaml`
- `.roadmap/ORCHESTRATOR_CONTRACT.yaml`
- `.roadmap/schemas/`

Do not assume all artifacts exist.

Before governed execution, read the available `.roadmap/` artifacts required to understand the current task, state, and runtime policy.

For read-only requests, inspect only what is necessary to answer safely.

---

## Core ESAA Principle

Agents execute or propose technical work.

The ESAA runtime, harness, or orchestrator governs state transitions.

Do not bypass the event log.

Do not silently mutate roadmap state.

Do not mark work as complete merely because files were changed.

If event log and roadmap projection disagree, treat `.roadmap/activity.jsonl` as authoritative and report the inconsistency.

---

## Harness-Aware Rule

This repository may be operated by a harness/orchestrator.

When a harness is responsible for ESAA state transitions:

- do the technical work;
- return a clear completion report;
- do not manually admit state transitions unless explicitly instructed;
- do not invent events;
- do not mark tasks as `done`.

When the repository policy explicitly requires the agent to write ESAA events directly:

- append events only according to the current ESAA contract;
- preserve append-only semantics;
- do not rewrite previous events;
- do not collapse lifecycle steps.

When uncertain, prefer safety:

- do not mutate ESAA state;
- report the uncertainty as a blocker.

---

## Interaction Modes

There are two valid interaction modes:

1. Read-only mode.
2. Governed execution mode.

Correctly identifying the mode is mandatory.

---

## 1. Read-only Mode

Use read-only mode when the user asks to:

- inspect;
- explain;
- summarize;
- diagnose;
- validate understanding;
- read roadmap files;
- read ESAA contracts;
- review project state without changing it.

In read-only mode:

- do not select a task;
- do not append `claim`;
- do not append `complete`;
- do not append `review`;
- do not update roadmap projections;
- do not modify project files;
- do not create tasks;
- do not create a task just to understand ESAA;
- report `Task ID: N/A`.

Verification is allowed in read-only mode only if it does not modify files.

For read-only requests, ESAA closure is not applicable because no governed state transition is being performed.

Use this exact closure wording in the final report:

ESAA closure status: Not applicable — read-only request. No governed state transition was required.

---

## 2. Governed Execution Mode

Use governed execution mode when the user asks to:

- implement;
- fix;
- refactor;
- generate project files;
- update code;
- update tests;
- complete a roadmap task;
- execute a specific ESAA task;
- perform a change that modifies files or ESAA state.

In governed execution mode:

- work on exactly one task;
- use the task explicitly provided by the user when one is provided;
- if no task is provided, select exactly one eligible task according to `.roadmap/init.yaml` and the current roadmap state;
- do not invent task IDs;
- do not create a separate task for understanding ESAA;
- do not execute multiple unrelated tasks in one run;
- do not mutate tasks already marked as `done`;
- preserve the distinction between `claim`, `complete`, and `review`;
- do not collapse lifecycle steps.

If no eligible task can be selected, do not proceed with technical changes. Report the blocker.

---

## Task Selection Rules

Before technical execution:

1. Determine whether the request is read-only or governed execution.
2. Read `.roadmap/init.yaml` if it exists.
3. Read the relevant roadmap projection.
4. Read the current event log from `.roadmap/activity.jsonl`.
5. If governed execution, identify exactly one task.
6. Verify that the task is not already `done`.
7. Verify that dependencies are satisfied.
8. If dependencies are not satisfied, report a blocker.
9. If the task cannot be safely selected, stop and report a blocker.

Do not modify files before the task is selected and validated.

---

## Agent Responsibility

The agent is responsible for technical execution.

The agent may:

- inspect allowed project files;
- modify files required by the selected task;
- add or update tests;
- run commands;
- report blockers;
- produce evidence of completion.

The agent must:

- work only on the selected task;
- preserve completed work;
- list changed files;
- list tests executed;
- explain why tests were not run, if applicable;
- report blockers instead of hiding them;
- follow the ESAA lifecycle required by the repository;
- provide a clear final report.

---

## Forbidden Actions

Do not:

- invent task IDs;
- create tasks only to understand ESAA;
- mutate tasks already marked as `done`;
- directly rewrite completed history;
- bypass `.roadmap/activity.jsonl`;
- silently change roadmap projections without respecting event-log policy;
- mark a task as complete without evidence;
- perform `review` unless explicitly assigned the reviewer/orchestrator role;
- claim success if verification failed;
- claim success if ESAA closure was skipped;
- say tests passed unless they were actually executed and passed;
- treat a read-only request as governed execution.

---

## ESAA Lifecycle

The standard lifecycle is:

claim -> complete -> review

The technical executor may perform `claim`, `complete`, or `issue.report` only when allowed by the current runtime policy.

The technical executor must not perform `review` unless the user or runtime explicitly assigns reviewer/orchestrator responsibility.

If the repository policy requires the agent to write ESAA events directly, do so exactly according to the current contract.

If the repository policy delegates event writing to a harness/orchestrator, return the required structured completion report and do not manually admit state transitions.

When in doubt:

- do not invent events;
- do not mark `done`;
- do not rewrite history;
- report the uncertainty as a blocker.

---

## Completion Protocol

Do not stop after code changes.

Before final response in governed execution mode, verify:

1. the selected task ID is known;
2. the technical work was performed;
3. changed files are listed;
4. tests were run or a reason is provided;
5. ESAA event/projection policy was followed;
6. no `done` task was mutated;
7. no lifecycle step was collapsed;
8. blockers are reported, if any;
9. ESAA verification was run when available and appropriate.

A task is not complete merely because implementation work was done.

A task is complete only when ESAA closure is satisfied according to the current repository policy.

If ESAA closure cannot be satisfied, report `blocked` or `failed`. Do not claim success.

---

## Activity Log Policy

The event log is the source of truth:

- `.roadmap/activity.jsonl`

If direct event writing is allowed by the current ESAA runtime policy:

- append events;
- do not rewrite prior events;
- use valid event types;
- reference the exact task ID;
- include changed files and evidence when completing work;
- preserve append-only semantics.

If direct event writing is not allowed:

- do not modify `.roadmap/activity.jsonl`;
- return a structured completion report for the harness/orchestrator.

Never fabricate event history.

Never rewrite previous events to make the current state look valid.

---

## Roadmap Projection Policy

Roadmap files are projections/read models.

Examples may include:

- `.roadmap/roadmap.json`
- `.roadmap/issues.json`
- `.roadmap/lessons.json`

If the runtime policy allows direct projection updates:

- update projections only after the corresponding event policy is satisfied;
- keep projection state consistent with `.roadmap/activity.jsonl`;
- do not mark tasks as `done` without a valid lifecycle path.

If projection updates are generated by the harness/orchestrator:

- do not update roadmap projections directly;
- report the technical result and allow the runtime to project state.

If activity log and roadmap projection disagree:

- treat `.roadmap/activity.jsonl` as authoritative;
- report the mismatch;
- do not silently fix it unless the user requested governed execution for that correction.

---

## Verification

Verification is distinct from application tests.

Verification checks ESAA consistency.

Tests check application behavior.

Verification is allowed in read-only mode only when it does not modify files.

When available, run the repository verification command after governed execution.

Possible commands may include:

- `esaa verify`
- `PYTHONPATH=src python -m esaa --root . verify`
- a project-specific equivalent

If verification reports mismatch, do not silently fix it unless the user requested governed execution.

If no verification command exists, say so explicitly.

Do not claim full ESAA success if verification failed, was unavailable, or was not run.

Report the limitation clearly.

---

## Tests

When changing code, run the most relevant test command available.

If tests are not obvious, inspect project files for commands, such as:

- `package.json`
- `pyproject.toml`
- `pytest.ini`
- `Makefile`
- `composer.json`
- README files

If tests cannot be run, explain why.

Do not say tests passed unless they were actually executed and passed.

Do not put ESAA verification under `Tests run`. Report it separately under `ESAA verification`.

---

## Final Response Format

Use this format for every response:

- Task ID: <task_id or N/A>
- Summary: <brief summary>
- Changed files: <list or Nenhum>
- Tests run: <commands/results or Nenhum>
- ESAA verification: <command/result or Not run>
- ESAA closure status: <satisfied / not applicable / blocked / failed>
- Blockers, if any: <list or Nenhum>

For read-only mode:

- Task ID: N/A
- Changed files: Nenhum.
- Tests run: Nenhum.
- ESAA verification: Optional. If run, report command and result.
- ESAA closure status: Not applicable — read-only request. No governed state transition was required.

For governed execution mode:

- do not use `Task ID: N/A` unless no valid task could be selected;
- if no valid task could be selected, report a blocker;
- do not modify files when no valid task is selected;
- report changed files;
- report tests;
- report ESAA verification separately;
- report whether ESAA closure was satisfied, blocked, or failed.

---

## Preferred Read-only Final Report Example

- Task ID: N/A
- Summary: Inspected the requested ESAA artifacts in read-only mode.
- Changed files: Nenhum.
- Tests run: Nenhum.
- ESAA verification: Not run.
- ESAA closure status: Not applicable — read-only request. No governed state transition was required.
- Blockers, if any: Nenhum.

---

## Preferred Governed Execution Final Report Example

- Task ID: TASK-000
- Summary: Implemented the requested change for the selected task.
- Changed files: path/to/file.ext
- Tests run: `command` — passed.
- ESAA verification: `command` — passed.
- ESAA closure status: satisfied.
- Blockers, if any: Nenhum.

---

## Minimal Rule

If you remember only one rule, use this:

Code changes are not task completion. A task is complete only after ESAA closure is satisfied.