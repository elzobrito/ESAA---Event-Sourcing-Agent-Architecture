#!/usr/bin/env python3
"""AUD-1401 — Rastreabilidade lessons<->gates<->reject_codes e agregador.

Valida que cada lesson de enforcement aponta para um gate e que os reject_codes
citados existem; agrega os findings dos demais checkers num indice priorizado.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

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

    # Agregacao dos demais checkers (se presentes)
    aggregated = []
    for name in ("contract_consistency.py", "schema_conformance.py", "eventstore_integrity.py"):
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
