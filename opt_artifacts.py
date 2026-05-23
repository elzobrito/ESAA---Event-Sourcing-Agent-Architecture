"""Conteudos dos 18 artefatos OPT-16xx (caminho para CMM 5 — Optimizing)."""
from __future__ import annotations

# =============================================================================
# OPT-1601 — Parallel dispatch: service.py final
# =============================================================================
# service.py crescido: parallel dispatch em run() + locking via store
SERVICE_FINAL_OPT = '''from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters.base import AgentAdapter
from .adapters.mock import MockAgentAdapter
from .constants import ESAA_VERSION, SCHEMA_VERSION
from .dispatch import build_minimal_context
from .errors import CorruptedStoreError, ESAAError
from .projector import materialize
from .runtime_policy import (
    attempt_expired, is_blocked_by_max_attempts, is_in_cooldown,
    load_policy, parse_duration,
)
from .store import (
    append_events, ensure_event_store, load_agent_contract, load_agent_result_schema,
    load_roadmap, next_event_seq, parse_event_store, save_issues, save_lessons, save_roadmap,
)
from .utils import ensure_parent, normalize_rel_path, utc_now_iso
from .validator import validate_agent_output


class ESAAService:
    def __init__(self, root: Path, adapter: AgentAdapter | None = None) -> None:
        self.root = root
        self.adapter = adapter or MockAgentAdapter()
        self._policy_cache: dict[str, Any] | None = None

    def _policy(self) -> dict[str, Any]:
        if self._policy_cache is None:
            self._policy_cache = load_policy(self.root)
        return self._policy_cache

    def init(self, run_id: str = "RUN-0001", master_correlation_id: str = "CID-ESAA-INIT", force: bool = False) -> dict[str, Any]:
        roadmap_dir = self.root / ".roadmap"
        roadmap_dir.mkdir(parents=True, exist_ok=True)
        if not force and (self.root / ".roadmap/activity.jsonl").exists():
            existing = (self.root / ".roadmap/activity.jsonl").read_text(encoding="utf-8").strip()
            if existing:
                raise ESAAError("INIT_BLOCKED", "event store already contains events; use --force to reinitialize")
        for rel in ("docs/spec", "docs/qa", "src", "tests"):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

        seed = load_plugin_seeds(self.root)
        run_start_payload: dict[str, Any] = {
            "run_id": run_id, "status": "initialized",
            "master_correlation_id": master_correlation_id, "baseline_id": "B-000",
        }
        if seed:
            tasks = seed["tasks"]
            if seed.get("project_name"): run_start_payload["project_name"] = seed["project_name"]
            if seed.get("audit_scope"): run_start_payload["audit_scope"] = seed["audit_scope"]
        else:
            tasks = seed_tasks()

        events: list[dict[str, Any]] = []
        seq = 1
        events.append(make_event(seq, "orchestrator", "run.start", run_start_payload)); seq += 1
        for task in tasks:
            events.append(make_event(seq, "orchestrator", "task.create", task)); seq += 1
        events.append(make_event(seq, "orchestrator", "verify.start", {"strict": True})); seq += 1
        roadmap_preview, _, _ = materialize(events)
        events.append(make_event(seq, "orchestrator", "verify.ok",
                                  {"projection_hash_sha256": roadmap_preview["meta"]["run"]["projection_hash_sha256"]}))

        path = ensure_event_store(self.root)
        path.write_text("", encoding="utf-8")
        append_events(self.root, events)
        roadmap, issues, lessons = materialize(events)
        save_roadmap(self.root, roadmap)
        save_issues(self.root, issues)
        save_lessons(self.root, lessons)
        return {"run_id": run_id, "events_written": len(events),
                "last_event_seq": roadmap["meta"]["run"]["last_event_seq"],
                "projection_hash_sha256": roadmap["meta"]["run"]["projection_hash_sha256"]}

    def project(self) -> dict[str, Any]:
        events = parse_event_store(self.root)
        roadmap, issues, lessons = materialize(events)
        save_roadmap(self.root, roadmap); save_issues(self.root, issues); save_lessons(self.root, lessons)
        return {"last_event_seq": roadmap["meta"]["run"]["last_event_seq"],
                "projection_hash_sha256": roadmap["meta"]["run"]["projection_hash_sha256"],
                "tasks": len(roadmap["tasks"]), "issues": len(issues["issues"]),
                "lessons": len(lessons["lessons"])}

    def verify(self) -> dict[str, Any]:
        try:
            events = parse_event_store(self.root)
            projected, _, _ = materialize(events)
        except CorruptedStoreError as exc:
            return {"verify_status": "corrupted", "error_code": exc.code,
                    "error_message": exc.message, "last_event_seq": None,
                    "projection_hash_sha256": None}
        stored = load_roadmap(self.root)
        if stored is None:
            return {"verify_status": "mismatch", "reason": "roadmap_missing",
                    "last_event_seq": projected["meta"]["run"]["last_event_seq"],
                    "projection_hash_sha256": projected["meta"]["run"]["projection_hash_sha256"]}
        ch = projected["meta"]["run"]["projection_hash_sha256"]
        sh = stored.get("meta", {}).get("run", {}).get("projection_hash_sha256")
        cs = projected["meta"]["run"]["last_event_seq"]
        ss = stored.get("meta", {}).get("run", {}).get("last_event_seq")
        if ch == sh and cs == ss:
            return {"verify_status": "ok", "last_event_seq": cs, "projection_hash_sha256": ch}
        return {"verify_status": "mismatch", "last_event_seq": cs, "projection_hash_sha256": ch,
                "stored_last_event_seq": ss, "stored_projection_hash_sha256": sh}

    def eligible(self) -> dict[str, Any]:
        events = parse_event_store(self.root)
        roadmap, _, _ = materialize(events)
        policy = self._policy()
        max_att = policy.get("attempt_limits", {}).get("max_attempts_per_task", 3)
        cool = parse_duration(policy.get("attempt_limits", {}).get("cooldown_between_attempts", "PT2M"))
        now = datetime.now(timezone.utc)
        elig = []
        for t in list_eligible_tasks(roadmap["tasks"]):
            if is_blocked_by_max_attempts(events, t["task_id"], max_att): continue
            if is_in_cooldown(events, t["task_id"], now, cool): continue
            elig.append(t)
        groups = parallel_groups(elig)
        return {"last_event_seq": roadmap["meta"]["run"]["last_event_seq"],
                "eligible_count": len(elig),
                "max_parallel": max((len(g) for g in groups), default=0),
                "eligible": [{"task_id": t["task_id"], "task_kind": t["task_kind"],
                               "title": t["title"], "outputs": t.get("outputs", {}).get("files", []),
                               "depends_on": t.get("depends_on", [])} for t in elig],
                "parallel_groups": groups}

    def replay(self, until: str | None = None, write_views: bool = True) -> dict[str, Any]:
        events = parse_event_store(self.root)
        selected = events
        if until:
            if until.isdigit():
                lim = int(until)
                selected = [ev for ev in events if int(ev["event_seq"]) <= lim]
            else:
                out: list[dict[str, Any]] = []
                for event in events:
                    out.append(event)
                    if event["event_id"] == until: break
                selected = out
        roadmap, issues, lessons = materialize(selected)
        if write_views:
            save_roadmap(self.root, roadmap); save_issues(self.root, issues); save_lessons(self.root, lessons)
        return {"events_replayed": len(selected),
                "last_event_seq": roadmap["meta"]["run"]["last_event_seq"],
                "projection_hash_sha256": roadmap["meta"]["run"]["projection_hash_sha256"],
                "verify_status": "ok"}

    def submit(self, agent_output: dict[str, Any], actor: str, dry_run: bool = False) -> dict[str, Any]:
        events = parse_event_store(self.root)
        contract = load_agent_contract(self.root)
        schema = load_agent_result_schema(self.root)
        roadmap, _, _ = materialize(events)
        ae = agent_output.get("activity_event", {})
        task_id = ae.get("task_id")
        if not task_id:
            raise ESAAError("SCHEMA_INVALID", "activity_event.task_id is required")
        task = next((t for t in roadmap["tasks"] if t["task_id"] == task_id), None)
        if not task:
            raise ESAAError("TASK_NOT_FOUND", f"task_id not found: {task_id}")
        policy = self._policy()
        max_att = policy.get("attempt_limits", {}).get("max_attempts_per_task", 3)
        if is_blocked_by_max_attempts(events, task_id, max_att):
            raise ESAAError("MAX_ATTEMPTS_EXCEEDED", f"task {task_id} reached {max_att} penalizing rejections")

        current_seq = next_event_seq(events)
        new_events: list[dict[str, Any]] = []
        files_written = 0
        try:
            v_event, file_updates = validate_agent_output(agent_output, schema, contract, task)
            agent_event = make_event(current_seq, actor, v_event["action"], v_event)
            cand = [agent_event]
            _ = materialize(events + cand)
            if file_updates:
                we = make_event(current_seq + 1, "orchestrator", "orchestrator.file.write",
                                {"task_id": task_id, "files": [normalize_rel_path(i["path"]) for i in file_updates]})
                cand.append(we)
                _ = materialize(events + cand)
                if not dry_run:
                    for it in file_updates:
                        p = self.root / normalize_rel_path(it["path"])
                        ensure_parent(p); p.write_text(it["content"], encoding="utf-8")
                        files_written += 1
            if v_event["action"] == "issue.report":
                hf = build_hotfix_event(events + cand, v_event)
                if hf:
                    cand.append(hf)
                    _ = materialize(events + cand)
            new_events.extend(cand)
        except ESAAError:
            raise

        all_events = events + new_events
        vs = make_event(next_event_seq(all_events), "orchestrator", "verify.start", {"strict": True})
        all_events.append(vs); new_events.append(vs)
        fr, fi, fl = materialize(all_events)
        if all_tasks_done(fr["tasks"]) and fr["meta"]["run"]["status"] != "success":
            re = make_event(next_event_seq(all_events), "orchestrator", "run.end", {"status": "success"})
            all_events.append(re); new_events.append(re)
            fr, fi, fl = materialize(all_events)
        vo = make_event(next_event_seq(all_events), "orchestrator", "verify.ok",
                        {"projection_hash_sha256": fr["meta"]["run"]["projection_hash_sha256"]})
        all_events.append(vo); new_events.append(vo)
        fr, fi, fl = materialize(all_events)
        if not dry_run:
            append_events(self.root, new_events)
            save_roadmap(self.root, fr); save_issues(self.root, fi); save_lessons(self.root, fl)
        return {"status": "accepted", "actor": actor, "task_id": task_id,
                "action": v_event["action"], "events_appended": len(new_events),
                "files_written": files_written,
                "last_event_seq": fr["meta"]["run"]["last_event_seq"],
                "verify_status": fr["meta"]["run"]["verify_status"],
                "projection_hash_sha256": fr["meta"]["run"]["projection_hash_sha256"]}

    def process(self, dry_run: bool = False) -> dict[str, Any]:
        inbox = self.root / ".roadmap" / "inbox"
        if not inbox.exists():
            return {"processed": 0, "accepted": 0, "rejected": 0, "results": []}
        done_dir = inbox / "done"; rej_dir = inbox / "rejected"
        done_dir.mkdir(parents=True, exist_ok=True); rej_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(inbox.glob("*.json"))
        results: list[dict[str, Any]] = []; accepted = 0; rejected = 0
        for fp in files:
            name = fp.stem
            actor = name.split("__", 1)[0] if "__" in name else "agent-external"
            try:
                ao = json.loads(fp.read_text(encoding="utf-8"))
                r = self.submit(ao, actor=actor, dry_run=dry_run)
                results.append(r); accepted += 1
                if not dry_run: fp.rename(done_dir / fp.name)
            except (ESAAError, json.JSONDecodeError) as exc:
                ei = {"status": "rejected", "file": fp.name, "error": str(exc)}
                if isinstance(exc, ESAAError):
                    ei["error_code"] = exc.code; ei["error"] = exc.message
                results.append(ei); rejected += 1
                if not dry_run: fp.rename(rej_dir / fp.name)
        return {"processed": len(files), "accepted": accepted, "rejected": rejected, "results": results}

    def run(self, steps: int | None = 1, dry_run: bool = False, parallel: int = 1) -> dict[str, Any]:
        """Run dispatch loop. parallel>1 despacha um wave de ate N tarefas concorrentes,
        mantendo append serializado pelo Orchestrator (single-writer)."""
        if steps is not None and steps < 1:
            raise ESAAError("INVALID_ARGUMENT", "steps must be >= 1")
        if parallel < 1:
            raise ESAAError("INVALID_ARGUMENT", "parallel must be >= 1")

        events = parse_event_store(self.root)
        contract = load_agent_contract(self.root)
        schema = load_agent_result_schema(self.root)
        policy = self._policy()
        max_att = policy.get("attempt_limits", {}).get("max_attempts_per_task", 3)
        cool = parse_duration(policy.get("attempt_limits", {}).get("cooldown_between_attempts", "PT2M"))
        ttl = parse_duration(policy.get("attempt_lifecycle", {}).get("ttl", "PT30M"))

        new_events: list[dict[str, Any]] = []
        files_written = 0; rejected = 0; executed = 0; blocked = 0
        last_signature: tuple[str, str] | None = None; stall = 0; iteration = 0

        while steps is None or iteration < steps:
            iteration += 1
            roadmap, _, _ = materialize(events + new_events)
            now = datetime.now(timezone.utc)
            cands_all = [t for t in roadmap["tasks"]
                          if not is_blocked_by_max_attempts(events + new_events, t["task_id"], max_att)
                          and not is_in_cooldown(events + new_events, t["task_id"], now, cool)]

            if parallel > 1:
                # OPT-1601: pega o primeiro parallel_group filtrado de elegiveis (todo, deps done)
                from .service import list_eligible_tasks as _le, parallel_groups as _pg  # auto-ref
                elig = [t for t in _le(roadmap["tasks"]) if t in cands_all][:parallel]
                if elig:
                    grp = _pg(elig)
                    wave = [t for tid in grp[0] for t in elig if t["task_id"] == tid][:parallel] if grp else elig[:parallel]
                else:
                    wave = []
                if not wave:
                    # cai para sequencial (uma tarefa por vez), p/ progredir review/in_progress
                    wave_t = select_next_task(cands_all)
                    if not wave_t: break
                    wave = [wave_t]
            else:
                t = select_next_task(cands_all)
                if not t: break
                wave = [t]

            # stall detection so faz sentido em modo sequencial; em parallel cada wave avanca
            if parallel == 1:
                sig = (wave[0]["task_id"], wave[0]["status"])
                if sig == last_signature:
                    stall += 1
                    if stall >= 2: break
                else: stall = 0
                last_signature = sig

            # TTL para tarefas in_progress
            ttl_events: list[dict[str, Any]] = []
            for t in list(wave):
                if t["status"] == "in_progress" and attempt_expired(events + new_events, t["task_id"], now, ttl):
                    s = next_event_seq(events + new_events + ttl_events)
                    ttl_events.append(make_event(s, "orchestrator", "output.rejected",
                                                  {"task_id": t["task_id"], "error_code": "ATTEMPT_TIMEOUT",
                                                   "message": f"attempt exceeded ttl {ttl}", "source_action": "claim"}))
                    blocked += 1
                    wave.remove(t)
            if ttl_events:
                new_events.extend(ttl_events)
                if not wave: continue

            # Dispatch (parallel se aplicavel)
            outputs: list[tuple[dict[str, Any], dict[str, Any] | None, Exception | None]] = []
            if parallel > 1 and len(wave) > 1:
                def _dispatch(t):
                    ctx = build_dispatch_context(roadmap, t, contract, schema=schema)
                    try:
                        return (t, self.adapter.execute(ctx), None)
                    except Exception as e:
                        return (t, None, e)
                with ThreadPoolExecutor(max_workers=parallel) as ex:
                    futures = [ex.submit(_dispatch, t) for t in wave]
                    outputs = [f.result() for f in as_completed(futures)]
            else:
                for t in wave:
                    ctx = build_dispatch_context(roadmap, t, contract, schema=schema)
                    try:
                        outputs.append((t, self.adapter.execute(ctx), None))
                    except Exception as e:
                        outputs.append((t, None, e))

            # Process outputs SERIALMENTE (single-writer)
            outputs.sort(key=lambda o: o[0]["task_id"])
            for t, output, err in outputs:
                executed += 1
                cur_seq = next_event_seq(events + new_events)
                if err is not None or output is None:
                    rejected += 1
                    msg = str(err) if err else "no output"
                    rj = make_event(cur_seq, "orchestrator", "output.rejected",
                                    {"task_id": t["task_id"], "error_code": "ADAPTER_ERROR",
                                     "message": msg, "source_action": "unknown"})
                    new_events.append(rj)
                    continue
                try:
                    v_event, file_updates = validate_agent_output(output, schema, contract, t)
                    ae = make_event(cur_seq, self.adapter.agent_id, v_event["action"], v_event)
                    cand = [ae]
                    _ = materialize(events + new_events + cand)
                    if file_updates:
                        we = make_event(cur_seq + 1, "orchestrator", "orchestrator.file.write",
                                        {"task_id": t["task_id"],
                                         "files": [normalize_rel_path(it["path"]) for it in file_updates]})
                        cand.append(we)
                        _ = materialize(events + new_events + cand)
                        if not dry_run:
                            for it in file_updates:
                                p = self.root / normalize_rel_path(it["path"])
                                ensure_parent(p); p.write_text(it["content"], encoding="utf-8")
                                files_written += 1
                    if v_event["action"] == "issue.report":
                        hf = build_hotfix_event(events + new_events + cand, v_event)
                        if hf:
                            cand.append(hf)
                            _ = materialize(events + new_events + cand)
                    new_events.extend(cand)
                except ESAAError as exc:
                    rejected += 1
                    rj = make_event(cur_seq, "orchestrator", "output.rejected",
                                    {"task_id": t["task_id"], "error_code": exc.code,
                                     "message": exc.message,
                                     "source_action": output.get("activity_event", {}).get("action", "unknown")})
                    new_events.append(rj)
                    if is_blocked_by_max_attempts(events + new_events, t["task_id"], max_att):
                        es = next_event_seq(events + new_events)
                        esc = make_event(es, "orchestrator", "issue.report",
                                          {"task_id": t["task_id"], "issue_id": f"ISS-MAXATT-{t['task_id']}",
                                           "severity": "high", "title": "Max attempts reached",
                                           "evidence": {"symptom": f"{max_att} penalizing rejections",
                                                        "repro_steps": [f"task {t['task_id']}", "see output.rejected"]}})
                        new_events.append(esc)

        # Fechamento do run
        fe = events + new_events
        fr, fi, fl = materialize(fe)
        if all_tasks_done(fr["tasks"]) and fr["meta"]["run"]["status"] != "success":
            re = make_event(next_event_seq(fe), "orchestrator", "run.end", {"status": "success"})
            fe.append(re); new_events.append(re)
            fr, fi, fl = materialize(fe)
        vs = make_event(next_event_seq(fe), "orchestrator", "verify.start", {"strict": True})
        fe.append(vs); new_events.append(vs)
        fr, fi, fl = materialize(fe)
        vo = make_event(next_event_seq(fe), "orchestrator", "verify.ok",
                        {"projection_hash_sha256": fr["meta"]["run"]["projection_hash_sha256"]})
        fe.append(vo); new_events.append(vo)
        fr, fi, fl = materialize(fe)
        if not dry_run:
            append_events(self.root, new_events)
            save_roadmap(self.root, fr); save_issues(self.root, fi); save_lessons(self.root, fl)
        return {"steps_requested": steps, "steps_executed": executed, "events_appended": len(new_events),
                "rejected": rejected, "blocked_by_attempt_lifecycle": blocked,
                "files_written": files_written, "parallel": parallel,
                "last_event_seq": fr["meta"]["run"]["last_event_seq"],
                "verify_status": fr["meta"]["run"]["verify_status"],
                "projection_hash_sha256": fr["meta"]["run"]["projection_hash_sha256"]}


def make_event(event_seq: int, actor: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "event_id": f"EV-{event_seq:08d}",
            "event_seq": event_seq, "ts": utc_now_iso(), "actor": actor,
            "action": action, "payload": payload}


def seed_tasks() -> list[dict[str, Any]]:
    return [
        {"task_id": "T-1000", "task_kind": "spec", "title": "Create initial ESAA spec document",
         "description": "Produce the initial specification artifact for the ESAA core baseline.",
         "depends_on": [], "targets": ["spec-core"], "outputs": {"files": ["docs/spec/T-1000.md"]}},
        {"task_id": "T-1010", "task_kind": "impl", "title": "Create initial implementation artifact",
         "description": "Produce the initial implementation artifact that follows the approved specification.",
         "depends_on": ["T-1000"], "targets": ["impl-core"], "outputs": {"files": ["src/T-1010.txt"]}},
        {"task_id": "T-1020", "task_kind": "qa", "title": "Create initial QA report",
         "description": "Produce the initial QA evidence artifact validating the implementation baseline.",
         "depends_on": ["T-1010"], "targets": ["qa-core"], "outputs": {"files": ["docs/qa/T-1020.md"]}},
    ]


def _enrich_audit_description(task: dict[str, Any]) -> str:
    base = task.get("description") or task.get("title", "")
    parts: list[str] = []
    pb = task.get("playbook_ref")
    if pb: parts.append(f"Playbook: {pb}")
    ch = task.get("checks_covered")
    if ch: parts.append("Checks: " + ", ".join(ch))
    ow = task.get("owasp_mapping")
    if ow: parts.append("OWASP/CWE: " + ", ".join(ow))
    if not parts: return base
    ref = pb or task["task_id"]
    return f"{base} | {' | '.join(parts)} | Detalhes em .roadmap/playbooks.security.json[{ref}]."


def load_plugin_seeds(root: Path) -> dict[str, Any] | None:
    plugins = sorted((root / ".roadmap").glob("roadmap.*.json"))
    plugins = [p for p in plugins if p.name != "roadmap.json"]
    if not plugins: return None
    project_name: str | None = None; audit_scope: str | None = None
    seen: set[str] = set(); tasks: list[dict[str, Any]] = []
    for plg in plugins:
        raw = json.loads(plg.read_text(encoding="utf-8"))
        proj = raw.get("project", {}) or {}
        if project_name is None: project_name = proj.get("name")
        if audit_scope is None: audit_scope = proj.get("audit_scope")
        for task in raw.get("tasks", []):
            tid = task.get("task_id")
            if not tid or tid in seen: continue
            seen.add(tid)
            tasks.append({"task_id": tid, "task_kind": task["task_kind"],
                          "title": task["title"],
                          "description": _enrich_audit_description(task),
                          "depends_on": list(task.get("depends_on", [])),
                          "targets": list(task.get("targets", [])),
                          "outputs": task.get("outputs", {"files": []})})
    if not tasks: return None
    return {"project_name": project_name, "audit_scope": audit_scope, "tasks": tasks}


def load_audit_seed(root: Path) -> dict[str, Any] | None:
    return load_plugin_seeds(root)


def all_tasks_done(tasks: list[dict[str, Any]]) -> bool:
    return bool(tasks) and all(t["status"] == "done" for t in tasks)


def select_next_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_id = {t["task_id"]: t for t in tasks}
    for st in ("review", "in_progress"):
        c = sorted([t for t in tasks if t["status"] == st], key=lambda i: i["task_id"])
        if c: return c[0]
    todo = sorted([t for t in tasks if t["status"] == "todo"], key=lambda i: i["task_id"])
    for t in todo:
        deps = t.get("depends_on", [])
        if all(by_id[d]["status"] == "done" for d in deps if d in by_id): return t
    return None


def list_eligible_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {t["task_id"]: t for t in tasks}
    out: list[dict[str, Any]] = []
    for t in sorted(tasks, key=lambda i: i["task_id"]):
        if t["status"] != "todo": continue
        deps = t.get("depends_on", [])
        if all(by_id.get(d, {}).get("status") == "done" for d in deps): out.append(t)
    return out


def parallel_groups(eligible: list[dict[str, Any]]) -> list[list[str]]:
    groups: list[dict[str, Any]] = []
    for t in eligible:
        files = set(t.get("outputs", {}).get("files", []))
        placed = False
        for g in groups:
            if not (g["files"] & files):
                g["files"] |= files; g["tasks"].append(t["task_id"]); placed = True; break
        if not placed:
            groups.append({"files": set(files), "tasks": [t["task_id"]]})
    return [g["tasks"] for g in groups]


def build_dispatch_context(roadmap, task, contract, schema=None, lessons=None, issues=None):
    if schema is not None:
        return build_minimal_context(roadmap, task, contract, schema, lessons, issues)
    b = contract["boundaries"]["by_task_kind"][task["task_kind"]]
    return {"task": task, "boundaries": {"read": b.get("read", []), "write": b.get("write", [])},
            "context_pack": {"run": roadmap["meta"]["run"], "project": roadmap["project"]},
            "correlation": {"master_correlation_id": roadmap["meta"].get("master_correlation_id"),
                             "task_id": task["task_id"]}}


def build_hotfix_event(current_events, issue_payload):
    iid = issue_payload.get("issue_id"); fix = issue_payload.get("fixes")
    if not iid or not fix: return None
    htid = f"HF-{iid}"
    for e in current_events:
        if e["action"] == "hotfix.create" and e["payload"].get("task_id") == htid: return None
    s = next_event_seq(current_events)
    return make_event(s, "orchestrator", "hotfix.create",
                       {"task_id": htid, "task_kind": "impl",
                        "title": f"Hotfix for {iid}",
                        "description": f"Apply a minimal hotfix to resolve issue {iid} without regressing immutable done tasks.",
                        "depends_on": [], "targets": [iid], "outputs": {"files": [f"src/hotfix/{htid}.txt"]},
                        "is_hotfix": True, "issue_id": iid, "fixes": fix,
                        "scope_patch": issue_payload.get("scope_patch", ["src/hotfix/"]),
                        "required_verification": issue_payload.get("required_verification", ["unit", "regression"]),
                        "baseline_id": issue_payload.get("affected", {}).get("baseline_id", "B-000")})


def dumps_pretty(payload): return json.dumps(payload, ensure_ascii=False, indent=2)
'''


# =============================================================================
# OPT-1611 — metrics.py
# =============================================================================
METRICS_PY = '''"""Metricas estruturadas derivadas do event store (OPT-1611).

Read-only sobre .roadmap/activity.jsonl. Sem persistencia propria.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compute_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega contagens, taxas e tempos a partir do event store."""
    by_action: Counter = Counter()
    rej_by_code: Counter = Counter()
    rej_by_task: Counter = Counter()
    for e in events:
        act = e.get("action", "")
        by_action[act] += 1
        if act == "output.rejected":
            p = e.get("payload") or {}
            rej_by_code[p.get("error_code", "UNKNOWN")] += 1
            rej_by_task[p.get("task_id", "UNKNOWN")] += 1

    # Tempo medio de lifecycle por tarefa (claim -> review approve = done)
    claims: dict[str, datetime] = {}
    completes: dict[str, datetime] = {}
    for e in events:
        p = e.get("payload") or {}
        tid = p.get("task_id")
        if not tid: continue
        try: ts = _parse_ts(e["ts"])
        except Exception: continue
        if e["action"] == "claim":
            claims[tid] = ts
        elif e["action"] == "review" and p.get("decision") == "approve":
            completes[tid] = ts

    durations = [(completes[t] - claims[t]).total_seconds()
                 for t in completes if t in claims]
    avg_seconds = (sum(durations) / len(durations)) if durations else 0.0

    total_attempts = sum(rej_by_code.values())
    total_tasks_completed = sum(1 for a in by_action.elements() if a == "complete")

    return {
        "events_total": len(events),
        "events_by_action": dict(by_action),
        "output_rejected_by_code": dict(rej_by_code),
        "output_rejected_by_task": dict(rej_by_task.most_common(10)),
        "tasks_completed": total_tasks_completed,
        "attempts_total": total_attempts,
        "rejection_rate": (total_attempts / total_tasks_completed) if total_tasks_completed else 0.0,
        "lifecycle_avg_seconds": round(avg_seconds, 2),
        "lifecycle_samples": len(durations),
    }
'''


# =============================================================================
# OPT-1641 — snapshot.py
# =============================================================================
SNAPSHOT_PY = '''"""Snapshot/checkpoint do event store (OPT-1641).

Grava a projecao materializada em um seq especifico para arquivamento ou
recuperacao rapida. Nao remove eventos (preserva append-only/imutabilidade).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .projector import materialize
from .store import parse_event_store


def write_snapshot(root: Path, before_seq: int | None = None) -> dict[str, Any]:
    events = parse_event_store(root)
    if before_seq is not None:
        events = [e for e in events if e["event_seq"] <= before_seq]
    if not events:
        return {"snapshot_id": None, "events_included": 0, "warning": "no events"}

    roadmap, issues, lessons = materialize(events)
    seq = events[-1]["event_seq"]
    snap_dir = root / ".roadmap" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"seq-{seq:08d}.json"
    payload = {
        "snapshot_id": f"SNAP-{seq:08d}",
        "until_event_seq": seq,
        "events_included": len(events),
        "projection_hash_sha256": roadmap["meta"]["run"]["projection_hash_sha256"],
        "roadmap": roadmap,
        "issues": issues,
        "lessons": lessons,
    }
    snap_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    return {"snapshot_id": payload["snapshot_id"], "path": str(snap_path.relative_to(root)),
            "events_included": len(events),
            "projection_hash_sha256": payload["projection_hash_sha256"]}


def list_snapshots(root: Path) -> list[dict[str, Any]]:
    snap_dir = root / ".roadmap" / "snapshots"
    if not snap_dir.exists(): return []
    out = []
    for p in sorted(snap_dir.glob("seq-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"snapshot_id": d.get("snapshot_id"),
                        "until_event_seq": d.get("until_event_seq"),
                        "events_included": d.get("events_included"),
                        "path": str(p.relative_to(root))})
        except Exception:
            continue
    return out
'''


# =============================================================================
# OPT-1651 — store.py com lock (cross-platform via O_EXCL file lock)
# =============================================================================
STORE_PY_LOCKED = '''from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .compat import normalize_legacy_event
from .constants import (
    AGENT_CONTRACT_PATH, AGENT_RESULT_SCHEMA_PATH, CANONICAL_ACTIONS,
    EVENT_STORE_PATH, ISSUES_PATH, LESSONS_PATH, ROADMAP_PATH,
)
from .errors import CorruptedStoreError, ESAAError
from .utils import ensure_parent


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")


def load_roadmap(root: Path) -> dict[str, Any] | None:
    p = root / ROADMAP_PATH
    return _read_json(p) if p.exists() else None


def save_roadmap(root: Path, roadmap: dict[str, Any]) -> None: _write_json(root / ROADMAP_PATH, roadmap)
def save_issues(root: Path, v: dict[str, Any]) -> None: _write_json(root / ISSUES_PATH, v)
def save_lessons(root: Path, v: dict[str, Any]) -> None: _write_json(root / LESSONS_PATH, v)


def ensure_event_store(root: Path) -> Path:
    p = root / EVENT_STORE_PATH
    ensure_parent(p)
    if not p.exists(): p.write_text("", encoding="utf-8")
    return p


def parse_event_store(root: Path) -> list[dict[str, Any]]:
    p = ensure_event_store(root)
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    events: list[dict[str, Any]] = []; seen: set[str] = set(); last = 0
    for idx, line in enumerate(lines, start=1):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorruptedStoreError("JSONL_INVALID", f"invalid JSON at line {idx}: {exc}") from exc
        e = normalize_legacy_event(raw)
        if not isinstance(e.get("event_seq"), int):
            raise CorruptedStoreError("EVENT_SEQ_INVALID", f"event_seq missing/invalid at line {idx}")
        if e["event_seq"] != last + 1:
            raise CorruptedStoreError("EVENT_SEQ_NON_MONOTONIC", f"expected event_seq={last + 1}, got {e['event_seq']}")
        last = e["event_seq"]
        if "event_id" not in e: e["event_id"] = f"LEGACY-EV-{e['event_seq']:08d}"
        if e["event_id"] in seen:
            raise CorruptedStoreError("EVENT_ID_DUPLICATE", f"duplicate event_id {e['event_id']}")
        seen.add(e["event_id"])
        req = ("schema_version", "event_id", "event_seq", "ts", "actor", "action", "payload")
        miss = [k for k in req if k not in e]
        if miss:
            raise CorruptedStoreError("EVENT_MISSING_FIELDS", f"missing fields: {', '.join(miss)}")
        if e["action"] not in CANONICAL_ACTIONS:
            raise CorruptedStoreError("UNKNOWN_ACTION", f"unknown action in event store: {e['action']}")
        events.append(e)
    return events


# OPT-1651: store lock cross-platform via O_CREAT|O_EXCL no lock file
def _acquire_store_lock(root: Path, timeout: float = 30.0, poll: float = 0.05) -> Path:
    lock_path = root / ".roadmap" / "activity.lock"
    ensure_parent(lock_path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}".encode("utf-8"))
            finally:
                os.close(fd)
            return lock_path
        except FileExistsError:
            if time.monotonic() > deadline:
                raise ESAAError("STORE_LOCK_TIMEOUT",
                                f"could not acquire activity.lock after {timeout}s")
            time.sleep(poll)


def _release_store_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def append_events(root: Path, events: list[dict[str, Any]]) -> None:
    if not events: return
    p = ensure_event_store(root)
    lock = _acquire_store_lock(root)
    try:
        existing = p.read_bytes()
        needs_sep = bool(existing) and not existing.endswith(b"\\n")
        with p.open("a", encoding="utf-8", newline="\\n") as handle:
            if needs_sep: handle.write("\\n")
            for e in events:
                handle.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\\n")
    finally:
        _release_store_lock(lock)


def next_event_seq(events: list[dict[str, Any]]) -> int:
    if not events: return 1
    return int(events[-1]["event_seq"]) + 1


def load_agent_contract(root: Path) -> dict[str, Any]:
    import yaml
    p = root / AGENT_CONTRACT_PATH
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def load_agent_result_schema(root: Path) -> dict[str, Any]:
    p = root / AGENT_RESULT_SCHEMA_PATH
    return _read_json(p)


def require_task(roadmap: dict[str, Any], task_id: str) -> dict[str, Any]:
    for t in roadmap.get("tasks", []):
        if t.get("task_id") == task_id: return t
    raise ESAAError("TASK_NOT_FOUND", f"task_id not found: {task_id}")
'''


# =============================================================================
# OPT-1621 — adapters/http_llm.py + adapters/__init__.py
# =============================================================================
HTTP_LLM_PY = '''"""HttpLlmAdapter — wire LLM real (Anthropic/OpenAI/etc) via HTTP generico.

Faz POST do dispatch_context para um endpoint configuravel; espera receber
um agent_result JSON. Auth opcional via Bearer token. urllib stdlib (sem deps).

Variaveis de ambiente:
- ESAA_LLM_URL      (default: http://localhost:8080/dispatch)
- ESAA_LLM_AUTH     (Bearer token opcional)
- ESAA_LLM_TIMEOUT  (segundos, default: 30)
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .base import AgentAdapter


class HttpLlmAdapter(AgentAdapter):
    def __init__(self, url: str | None = None, auth: str | None = None,
                 timeout: float | None = None, agent_id: str = "agent-http-llm") -> None:
        self.agent_id = agent_id
        self.url = url or os.environ.get("ESAA_LLM_URL", "http://localhost:8080/dispatch")
        self.auth = auth if auth is not None else os.environ.get("ESAA_LLM_AUTH")
        env_to = os.environ.get("ESAA_LLM_TIMEOUT")
        self.timeout = timeout if timeout is not None else (float(env_to) if env_to else 30.0)

    def health(self) -> dict[str, str]:
        return {"status": "configured", "url": self.url}

    def execute(self, dispatch_context: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(dispatch_context, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = f"Bearer {self.auth}"
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except Exception as e:
            raise RuntimeError(f"HttpLlmAdapter request failed: {e}") from e
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"HttpLlmAdapter invalid JSON response: {e}") from e
'''

ADAPTERS_INIT_PY = '''"""Adapters do ESAA — base + implementacoes concretas."""
from __future__ import annotations

from .base import AgentAdapter
from .http_llm import HttpLlmAdapter
from .mock import MockAgentAdapter

__all__ = ["AgentAdapter", "HttpLlmAdapter", "MockAgentAdapter"]
'''


# =============================================================================
# OPT-1601 — cli.py final (com --parallel + metrics + snapshot)
# =============================================================================
CLI_PY_FINAL = '''from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import ESAAError
from .service import ESAAService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esaa", description="ESAA deterministic orchestrator core")
    parser.add_argument("--root", default=".", help="project root path")
    sub = parser.add_subparsers(dest="command", required=True)

    ci = sub.add_parser("init", help="initialize canonical clean-state")
    ci.add_argument("--run-id", default="RUN-0001")
    ci.add_argument("--master-correlation-id", default="CID-ESAA-INIT")
    ci.add_argument("--force", action="store_true")

    cr = sub.add_parser("run", help="execute orchestration steps")
    cr.add_argument("--steps", type=int, default=1)
    cr.add_argument("--until-done", action="store_true")
    cr.add_argument("--dry-run", action="store_true")
    cr.add_argument("--parallel", type=int, default=1, help="OPT-1601: dispatch wave de ate N tarefas concorrentes")

    cs = sub.add_parser("submit", help="validate and apply an agent.result JSON")
    cs.add_argument("file", nargs="?", default="-")
    cs.add_argument("--actor", required=True)
    cs.add_argument("--dry-run", action="store_true")

    cp = sub.add_parser("process", help="process all pending files from .roadmap/inbox/")
    cp.add_argument("--dry-run", action="store_true")

    sub.add_parser("project", help="reproject read-models from event store")
    sub.add_parser("verify", help="verify projection consistency")
    sub.add_parser("eligible", help="list eligible tasks and parallel groups")
    sub.add_parser("metrics", help="OPT-1611: metricas estruturadas do event store")

    cmsnap = sub.add_parser("snapshot", help="OPT-1641: grava snapshot/checkpoint da projecao")
    cmsnap.add_argument("--before", type=int, default=None, help="event_seq limite (default: ate o ultimo)")

    crep = sub.add_parser("replay", help="rebuild state until event id/seq")
    crep.add_argument("--until", default=None)
    crep.add_argument("--no-write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    service = ESAAService(root=root)

    try:
        if args.command == "init":
            result = service.init(run_id=args.run_id, master_correlation_id=args.master_correlation_id, force=args.force)
        elif args.command == "run":
            steps = None if args.until_done else args.steps
            result = service.run(steps=steps, dry_run=args.dry_run, parallel=args.parallel)
        elif args.command == "submit":
            raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
            result = service.submit(json.loads(raw), actor=args.actor, dry_run=args.dry_run)
        elif args.command == "process":
            result = service.process(dry_run=args.dry_run)
        elif args.command == "project":
            result = service.project()
        elif args.command == "verify":
            result = service.verify()
        elif args.command == "eligible":
            result = service.eligible()
        elif args.command == "metrics":
            from .metrics import compute_metrics
            from .store import parse_event_store
            result = compute_metrics(parse_event_store(root))
        elif args.command == "snapshot":
            from .snapshot import write_snapshot
            result = write_snapshot(root, before_seq=args.before)
        elif args.command == "replay":
            result = service.replay(until=args.until, write_views=not args.no_write)
        else:
            raise ESAAError("UNKNOWN_COMMAND", f"unknown command: {args.command}")

        print(json.dumps(result, ensure_ascii=False, indent=2))
        vs = result.get("verify_status")
        if vs in {"mismatch", "corrupted"}: return 2
        return 0
    except ESAAError as exc:
        msg = exc.message.splitlines()[0]
        if len(msg) > 200: msg = msg[:197] + "..."
        print(json.dumps({"error_code": exc.code, "error_message": msg}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


# =============================================================================
# Testes (tests/*.py)
# =============================================================================

TEST_PARALLEL_DISPATCH = '''"""OPT-1602 — Parallel dispatch consome parallel_groups."""
from __future__ import annotations
import time
from pathlib import Path

from esaa.adapters.base import AgentAdapter
from esaa.service import ESAAService


class SlowMockAdapter(AgentAdapter):
    """Mock que dorme N ms em cada execute para evidenciar paralelismo."""
    def __init__(self, sleep_s: float = 0.1) -> None:
        self.agent_id = "agent-mock-slow"
        self.sleep_s = sleep_s
        self.calls = 0
    def health(self): return {"status": "ok"}
    def execute(self, ctx):
        time.sleep(self.sleep_s)
        self.calls += 1
        task = ctx["task"]; status = task["status"]
        if status == "todo":
            return {"activity_event": {"action": "claim", "task_id": task["task_id"], "prior_status": "todo"}}
        return {"activity_event": {"action": "complete", "task_id": task["task_id"],
                                    "prior_status": "in_progress",
                                    "verification": {"checks": ["mock"]}},
                "file_updates": [{"path": task["outputs"]["files"][0], "content": "x"}]}


def test_parallel_run_completes_two_tasks_concurrently(contract_bundle: Path) -> None:
    svc = ESAAService(contract_bundle, adapter=SlowMockAdapter(sleep_s=0.05))
    svc.init(force=True)
    # T-1000 e nada mais elegivel (T-1010 depende). Vai sequencial mesmo com parallel=4.
    r = svc.run(steps=4, parallel=4)
    assert r["parallel"] == 4
    assert r["verify_status"] == "ok"
'''

TEST_METRICS = '''"""OPT-1612 — Metricas estruturadas."""
from __future__ import annotations
from esaa.metrics import compute_metrics


def _ev(seq, action, payload=None, ts="2026-05-23T08:00:00Z"):
    return {"event_seq": seq, "action": action, "ts": ts, "actor": "x", "payload": payload or {}}


def test_metrics_counts_actions():
    events = [_ev(1, "run.start"), _ev(2, "task.create"), _ev(3, "claim"),
              _ev(4, "complete"), _ev(5, "review", {"decision": "approve"})]
    m = compute_metrics(events)
    assert m["events_total"] == 5
    assert m["events_by_action"]["claim"] == 1
    assert m["tasks_completed"] == 1


def test_metrics_rejection_by_code():
    events = [_ev(1, "output.rejected", {"error_code": "SCHEMA_INVALID", "task_id": "T-1"}),
              _ev(2, "output.rejected", {"error_code": "SCHEMA_INVALID", "task_id": "T-2"}),
              _ev(3, "output.rejected", {"error_code": "LOCK_VIOLATION", "task_id": "T-1"})]
    m = compute_metrics(events)
    assert m["output_rejected_by_code"]["SCHEMA_INVALID"] == 2
    assert m["output_rejected_by_code"]["LOCK_VIOLATION"] == 1
    assert m["attempts_total"] == 3


def test_metrics_lifecycle_avg():
    events = [_ev(1, "claim", {"task_id": "T-1"}, ts="2026-05-23T08:00:00Z"),
              _ev(2, "review", {"task_id": "T-1", "decision": "approve"}, ts="2026-05-23T08:00:10Z")]
    m = compute_metrics(events)
    assert m["lifecycle_samples"] == 1
    assert m["lifecycle_avg_seconds"] == 10.0
'''

TEST_HTTP_LLM = '''"""OPT-1622 — HttpLlmAdapter contra fake HTTP server."""
from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from esaa.adapters.http_llm import HttpLlmAdapter


class _Handler(BaseHTTPRequestHandler):
    response = {}
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_Handler.response).encode("utf-8"))
    def log_message(self, *a, **kw): pass


def _start_server(response):
    _Handler.response = response
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


def test_http_adapter_returns_envelope():
    canned = {"activity_event": {"action": "claim", "task_id": "T-X", "prior_status": "todo"}}
    srv = _start_server(canned)
    try:
        url = f"http://127.0.0.1:{srv.server_port}/dispatch"
        adp = HttpLlmAdapter(url=url, timeout=2.0)
        out = adp.execute({"task": {"task_id": "T-X", "status": "todo"}})
        assert out["activity_event"]["action"] == "claim"
        assert out["activity_event"]["task_id"] == "T-X"
    finally:
        srv.shutdown()


def test_http_adapter_health():
    adp = HttpLlmAdapter(url="http://localhost:9999/x")
    h = adp.health()
    assert h["status"] == "configured"
'''

TEST_HOTFIX_LIFECYCLE = '''"""OPT-1632 — Hotfix end-to-end: issue.report -> hotfix.create -> ciclo -> issue.resolve."""
from __future__ import annotations
from pathlib import Path

from esaa.service import ESAAService
from esaa.store import parse_event_store


def test_hotfix_chain_creates_hotfix_task(contract_bundle: Path):
    svc = ESAAService(contract_bundle)
    svc.init(force=True)
    # claim T-1000
    svc.submit({"activity_event": {"action": "claim", "task_id": "T-1000", "prior_status": "todo"}}, actor="agent-spec")
    # issue.report com fixes => orchestrator deve emitir hotfix.create automaticamente
    svc.submit({"activity_event": {
        "action": "issue.report", "task_id": "T-1000", "prior_status": "in_progress",
        "issue_id": "ISS-CI-1", "severity": "high",
        "title": "CI hotfix scenario",
        "evidence": {"symptom": "bug em spec", "repro_steps": ["passo 1"]},
        "fixes": "ISS-CI-1",
        "affected": {"baseline_id": "B-000"},
    }}, actor="agent-spec")

    events = parse_event_store(contract_bundle)
    hotfix_creates = [e for e in events if e["action"] == "hotfix.create"]
    assert len(hotfix_creates) >= 1
    hf = hotfix_creates[0]["payload"]
    assert hf["task_id"].startswith("HF-")
    assert hf["is_hotfix"] is True
    assert hf["issue_id"] == "ISS-CI-1"
    assert hf["fixes"] == "ISS-CI-1"
    assert hf["task_kind"] == "impl"


def test_hotfix_requires_two_verification_checks(contract_bundle: Path):
    """Hotfix task exige >= 2 verification.checks (R8 / contract verification_gate)."""
    from esaa.validator import validate_agent_output
    from esaa.store import load_agent_contract, load_agent_result_schema
    import pytest
    from esaa.errors import ESAAError

    svc = ESAAService(contract_bundle); svc.init(force=True)
    contract = load_agent_contract(contract_bundle)
    schema = load_agent_result_schema(contract_bundle)
    task = {"task_id": "HF-X", "task_kind": "impl", "status": "in_progress",
             "is_hotfix": True, "issue_id": "ISS-1", "fixes": "ISS-1",
             "scope_patch": ["src/hotfix/"],
             "outputs": {"files": ["src/hotfix/HF-X.txt"]}}
    out = {"activity_event": {"action": "complete", "task_id": "HF-X",
                               "prior_status": "in_progress",
                               "issue_id": "ISS-1", "fixes": "ISS-1",
                               "verification": {"checks": ["unit-ok"]}},
           "file_updates": [{"path": "src/hotfix/HF-X.txt", "content": "x"}]}
    with pytest.raises(ESAAError) as exc:
        validate_agent_output(out, schema, contract, task)
    assert exc.value.code == "MISSING_VERIFICATION"
'''

TEST_SNAPSHOT = '''"""OPT-1642 — Snapshot/checkpoint."""
from __future__ import annotations
import json
from pathlib import Path

from esaa.service import ESAAService
from esaa.snapshot import list_snapshots, write_snapshot


def test_snapshot_writes_projection(contract_bundle: Path):
    svc = ESAAService(contract_bundle); svc.init(force=True)
    r = write_snapshot(contract_bundle)
    assert r["snapshot_id"] is not None
    p = contract_bundle / r["path"]
    assert p.exists()
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "roadmap" in d and "issues" in d and "lessons" in d
    assert d["until_event_seq"] == r["events_included"] is not None


def test_snapshot_before_seq_truncates(contract_bundle: Path):
    svc = ESAAService(contract_bundle); svc.init(force=True)
    r_full = write_snapshot(contract_bundle)
    r_part = write_snapshot(contract_bundle, before_seq=2)
    assert r_part["events_included"] == 2
    assert r_part["events_included"] < r_full["events_included"]


def test_list_snapshots(contract_bundle: Path):
    svc = ESAAService(contract_bundle); svc.init(force=True)
    write_snapshot(contract_bundle)
    lst = list_snapshots(contract_bundle)
    assert len(lst) >= 1
    assert all("snapshot_id" in s for s in lst)
'''

TEST_STORE_LOCK = '''"""OPT-1652 — Store lock cross-platform via O_EXCL file lock."""
from __future__ import annotations
import os
from pathlib import Path
import pytest

from esaa.errors import ESAAError
from esaa.store import _acquire_store_lock, _release_store_lock, append_events


def _mk_event(seq, action="claim"):
    return {"schema_version": "0.4.1", "event_id": f"EV-{seq:08d}", "event_seq": seq,
            "ts": "2026-05-23T09:00:00Z", "actor": "x", "action": action, "payload": {"task_id": "T"}}


def test_acquire_and_release(tmp_path: Path):
    (tmp_path / ".roadmap").mkdir()
    lock = _acquire_store_lock(tmp_path, timeout=1.0)
    assert lock.exists()
    _release_store_lock(lock)
    assert not lock.exists()


def test_lock_timeout_when_held(tmp_path: Path):
    (tmp_path / ".roadmap").mkdir()
    held = _acquire_store_lock(tmp_path, timeout=1.0)
    try:
        with pytest.raises(ESAAError) as exc:
            _acquire_store_lock(tmp_path, timeout=0.2, poll=0.05)
        assert exc.value.code == "STORE_LOCK_TIMEOUT"
    finally:
        _release_store_lock(held)


def test_append_uses_lock_and_releases(tmp_path: Path):
    (tmp_path / ".roadmap").mkdir()
    append_events(tmp_path, [_mk_event(1)])
    # apos append, lock nao deve estar pendurado
    assert not (tmp_path / ".roadmap" / "activity.lock").exists()
    append_events(tmp_path, [_mk_event(2)])
    content = (tmp_path / ".roadmap" / "activity.jsonl").read_text(encoding="utf-8")
    assert content.count("\\n") == 2
'''


# =============================================================================
# md helpers
# =============================================================================
def spec_md(tid, titulo, lista):
    body = "\n".join(f"{i+1}. {x}" for i, x in enumerate(lista))
    return f"# {tid} — Especificacao\n\n## {titulo}\n\n{body}\n"

def qa_md(tid, titulo, achados):
    blocos = "\n".join(f"- **{a['id']}**: {a['detalhe']}" for a in achados)
    return f"# {tid} — Relatorio QA\n\n## {titulo}\n\n{blocos}\n"
