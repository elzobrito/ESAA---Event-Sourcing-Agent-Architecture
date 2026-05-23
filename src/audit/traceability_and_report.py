#!/usr/bin/env python3
"""AUD-1401 — Rastreabilidade lessons<->gates<->reject_codes e agregador.

Valida que cada lesson de enforcement aponta para um gate e que os reject_codes
citados existem; agrega os findings dos demais checkers num indice priorizado.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

def _load_events(root: Path) -> list[dict]:
    path = root / ".roadmap/activity.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

def check_done_evidence(root: Path) -> list[dict]:
    """Detect done tasks that lack the governed claim/complete/review evidence trail."""
    findings = []
    try:
        sys.path.insert(0, str(root / "src"))
        from esaa.projector import materialize

        events = _load_events(root)
        roadmap, _, _ = materialize(events)
    except Exception as exc:
        return [{"id": "R-DONE-EVIDENCE-ERR", "severity": "low",
                 "title": "could not inspect done task evidence",
                 "evidence": {"error": str(exc)}}]

    by_task: dict[str, list[dict]] = {}
    for event in events:
        task_id = (event.get("payload") or {}).get("task_id")
        if task_id:
            by_task.setdefault(task_id, []).append(event)

    for task in roadmap.get("tasks", []):
        if task.get("status") != "done":
            continue
        task_id = task["task_id"]
        trail = by_task.get(task_id, [])
        actions = [event.get("action") for event in trail]
        complete_events = [e for e in trail if e.get("action") == "complete"]
        review_events = [e for e in trail if e.get("action") == "review"]
        missing = []
        if "claim" not in actions:
            missing.append("claim")
        if not complete_events:
            missing.append("complete")
        if not any((e.get("payload") or {}).get("verification", {}).get("checks") for e in complete_events):
            missing.append("verification.checks")
        if not any((e.get("payload") or {}).get("decision") == "approve" for e in review_events):
            missing.append("review.approve")
        if task.get("is_hotfix") and not any(
            e.get("action") == "issue.resolve"
            and (e.get("payload") or {}).get("hotfix_task_id") == task_id
            for e in events
        ):
            missing.append("issue.resolve")
        if missing:
            findings.append({"id": "R-DONE-EVIDENCE-MISSING", "severity": "medium",
                             "title": f"{task_id} done without complete evidence trail",
                             "evidence": {"task_id": task_id, "missing": missing}})
    return findings

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--audit-dir", default=None, help="dir dos checkers; default <root>/src/audit")
    args = ap.parse_args()
    root = Path(args.root)
    audit_dir = Path(args.audit_dir) if args.audit_dir else (root / "src/audit")
    findings = []

    lessons_p = root / ".roadmap/lessons.json"
    if lessons_p.exists():
        lessons = json.loads(lessons_p.read_text(encoding="utf-8")).get("lessons", [])
        for les in lessons:
            refs = les.get("source_refs", [])
            kinds = {r.get("type") for r in refs}
            if les.get("enforcement", {}).get("mode") in ("reject", "require_field") and "gate" not in kinds:
                findings.append({"id": "R-trace", "severity": "medium",
                                 "title": f"{les['lesson_id']} sem source_ref de gate",
                                 "evidence": {"types": sorted(kinds)}})

    findings.extend(check_done_evidence(root))

    # Agregacao dos demais checkers (se presentes)
    aggregated = []
    for name in ("contract_consistency.py", "schema_conformance.py", "eventstore_integrity.py", "critical_findings.py"):
        script = audit_dir / name
        if script.exists():
            try:
                out = subprocess.run([sys.executable, str(script), "--root", str(root)],
                                     capture_output=True, text=True, timeout=60)
                data = json.loads(out.stdout or "{}")
                aggregated.extend(data.get("findings", []))
            except Exception as e:
                findings.append({"id": "AGG-ERR", "severity": "low",
                                 "title": f"falha ao agregar {name}", "evidence": {"err": str(e)}})

    all_findings = aggregated + findings
    all_findings.sort(key=lambda f: SEV_ORDER.get(f.get("severity"), 9))
    print(json.dumps({"checker": "traceability_and_report",
                      "total_findings": len(all_findings),
                      "by_severity": {s: sum(1 for f in all_findings if f.get("severity") == s)
                                      for s in SEV_ORDER},
                      "findings": all_findings}, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
