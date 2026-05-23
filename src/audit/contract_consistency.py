#!/usr/bin/env python3
"""AUD-1001 — Verificador de consistência contrato/documento.

Audita drift de versão e divergência de vocabulário entre os artefatos
canônicos do ESAA. Read-only. Saída: JSON de findings.

Uso: python contract_consistency.py --root <repo_root>
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

DOC_REJECT_CODES = {
    "MISSING_CLAIM", "MISSING_COMPLETE", "MISSING_VERIFICATION",
    "PRIOR_STATUS_MISMATCH", "LOCK_VIOLATION", "ACTION_COLLAPSE",
    "IMMUTABLE_DONE_VIOLATION",
}
ENGINE_ERROR_CODES = {
    "SCHEMA_INVALID", "UNKNOWN_ACTION", "WORKFLOW_GATE", "BOUNDARY_VIOLATION",
    "IMMUTABLE_DONE", "LOCKED_TASK", "INVALID_TRANSITION", "NOT_LOCK_OWNER",
    "TASK_NOT_FOUND", "DUPLICATE_TASK", "ISSUE_NOT_FOUND",
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    findings = []

    def declared_version(path: str, pattern: str) -> str | None:
        p = root / path
        if not p.exists():
            return None
        m = re.search(pattern, p.read_text(encoding="utf-8"))
        return m.group(1) if m else None

    versions = {
        "AGENT_CONTRACT.yaml": declared_version(".roadmap/AGENT_CONTRACT.yaml", r'contract_version:\s*"([^"]+)"'),
        "ORCHESTRATOR_CONTRACT.yaml": declared_version(".roadmap/ORCHESTRATOR_CONTRACT.yaml", r'contract_version:\s*"([^"]+)"'),
        "agent_result.schema.json": declared_version(".roadmap/agent_result.schema.json", r'v(0\.\d\.\d)'),
        "constants.py(SCHEMA_VERSION)": declared_version("src/esaa/constants.py", r'SCHEMA_VERSION\s*=\s*"([^"]+)"'),
        "pyproject.toml": declared_version("pyproject.toml", r'version\s*=\s*"([^"]+)"'),
        "roadmap.schema.json(const)": declared_version(".roadmap/roadmap.schema.json", r'"const":\s*"(0\.\d\.\d)"'),
    }
    distinct = {v for v in versions.values() if v}
    if len(distinct) > 1:
        findings.append({
            "id": "R3", "severity": "high",
            "title": "Version drift entre contratos e engine/projeções",
            "evidence": versions,
            "recommendation": "Migrar engine (constants/pyproject/roadmap.schema) para 0.4.1.",
        })

    # Convenção de nome dos PARCER profiles
    roadmap_dir = root / ".roadmap"
    if roadmap_dir.exists():
        profiles = [p.name for p in roadmap_dir.glob("PARCER_PROFILE*")]
        dot = [n for n in profiles if n.startswith("PARCER_PROFILE.")]
        underscore = [n for n in profiles if n.startswith("PARCER_PROFILE_")]
        if dot and underscore:
            findings.append({
                "id": "R10", "severity": "low",
                "title": "Convencao de nome de PARCER profile inconsistente (ponto vs underscore)",
                "evidence": {"dot": dot, "underscore": underscore},
                "recommendation": "Padronizar para um unico separador.",
            })

    print(json.dumps({"checker": "contract_consistency", "findings": findings}, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
