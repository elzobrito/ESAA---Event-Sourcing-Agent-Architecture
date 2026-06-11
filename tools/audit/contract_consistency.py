#!/usr/bin/env python3
"""AUD-1001 â€” Verificador de consistÃªncia contrato/documento.

Audita drift de versÃ£o e divergÃªncia de vocabulÃ¡rio entre os artefatos
canÃ´nicos do ESAA. Read-only. SaÃ­da: JSON de findings.

Uso: python contract_consistency.py --root <repo_root>
"""

from __future__ import annotations
import argparse, json, re
from pathlib import Path

# M-04: vocabulario canonico de reject_codes vem de src/esaa/reject_codes.py.
# Importacao defensiva: se PYTHONPATH=src nao estiver setado, cai para fallback
# textual (mantem o checker funcional fora do dev environment).
try:
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from esaa.reject_codes import ALL_CODES as _RC_ALL, WORKFLOW_GATE_CODES as _RC_WG

    DOC_REJECT_CODES = frozenset(_RC_WG)
    ENGINE_ERROR_CODES = frozenset(_RC_ALL)
except Exception:
    DOC_REJECT_CODES = frozenset(
        {
            "MISSING_CLAIM",
            "MISSING_COMPLETE",
            "MISSING_VERIFICATION",
            "PRIOR_STATUS_MISMATCH",
            "LOCK_VIOLATION",
            "ACTION_COLLAPSE",
            "IMMUTABLE_DONE_VIOLATION",
        }
    )
    ENGINE_ERROR_CODES = frozenset(
        {
            "SCHEMA_INVALID",
            "UNKNOWN_ACTION",
            "WORKFLOW_GATE_VIOLATION",
            "BOUNDARY_VIOLATION",
            "IMMUTABLE_DONE_VIOLATION",
            "LOCK_VIOLATION",
            "TASK_NOT_FOUND",
            "DUPLICATE_TASK",
            "ISSUE_NOT_FOUND",
        }
    )


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

    protocol_versions = {
        "AGENT_CONTRACT.yaml": declared_version(
            ".roadmap/AGENT_CONTRACT.yaml", r'contract_version:\s*"([^"]+)"'
        ),
        "ORCHESTRATOR_CONTRACT.yaml": declared_version(
            ".roadmap/ORCHESTRATOR_CONTRACT.yaml", r'contract_version:\s*"([^"]+)"'
        ),
        "agent_result.schema.json": declared_version(".roadmap/agent_result.schema.json", r"v(0\.\d\.\d)"),
        "constants.py(SCHEMA_VERSION)": declared_version(
            "src/esaa/constants.py", r'SCHEMA_VERSION\s*=\s*"([^"]+)"'
        ),
        "roadmap.schema.json(const)": declared_version(
            ".roadmap/roadmap.schema.json", r'"const":\s*"(0\.\d\.\d)"'
        ),
    }
    package_version = declared_version("pyproject.toml", r'version\s*=\s*"([^"]+)"')
    distinct = {v for v in protocol_versions.values() if v}
    if len(distinct) > 1:
        findings.append(
            {
                "id": "R3",
                "severity": "high",
                "title": "Version drift entre contratos e engine/projeÃ§Ãµes",
                "evidence": protocol_versions,
                "recommendation": "Migrar contratos, schemas e constants.py para a mesma versao de protocolo.",
            }
        )
    if package_version and not package_version.startswith("0.5.0"):
        findings.append(
            {
                "id": "R-PACKAGE-VERSION",
                "severity": "low",
                "title": "Versao do pacote nao esta na linha publica beta esperada",
                "evidence": {"pyproject.toml": package_version, "protocol_versions": protocol_versions},
                "recommendation": "Manter pacote na linha 0.5.0b* enquanto o protocolo permanece em 0.4.1.",
            }
        )

    # ConvenÃ§Ã£o de nome dos PARCER profiles
    roadmap_dir = root / ".roadmap"
    if roadmap_dir.exists():
        profiles = [p.name for p in roadmap_dir.glob("PARCER_PROFILE*")]
        dot = [n for n in profiles if n.startswith("PARCER_PROFILE.")]
        underscore = [n for n in profiles if n.startswith("PARCER_PROFILE_")]
        if dot and underscore:
            findings.append(
                {
                    "id": "R10",
                    "severity": "low",
                    "title": "Convencao de nome de PARCER profile inconsistente (ponto vs underscore)",
                    "evidence": {"dot": dot, "underscore": underscore},
                    "recommendation": "Padronizar para um unico separador.",
                }
            )

    # FIX-1812: runner.metrics deve estar em todas as fontes canonicas
    rm_sources = {
        "AGENT_CONTRACT.yaml(reserved)": (
            "runner.metrics" in (root / ".roadmap/AGENT_CONTRACT.yaml").read_text(encoding="utf-8")
            if (root / ".roadmap/AGENT_CONTRACT.yaml").exists()
            else False
        ),
        "ORCHESTRATOR_CONTRACT.yaml(reserved)": (
            "runner.metrics" in (root / ".roadmap/ORCHESTRATOR_CONTRACT.yaml").read_text(encoding="utf-8")
            if (root / ".roadmap/ORCHESTRATOR_CONTRACT.yaml").exists()
            else False
        ),
        "constants.py(CANONICAL_ACTIONS)": (
            "runner.metrics" in (root / "src/esaa/constants.py").read_text(encoding="utf-8")
            if (root / "src/esaa/constants.py").exists()
            else False
        ),
        "AGENTS.md": (
            "runner.metrics" in (root / "AGENTS.md").read_text(encoding="utf-8")
            if (root / "AGENTS.md").exists()
            else False
        ),
        ".claude/CLAUDE.md": (
            "runner.metrics" in (root / ".claude/CLAUDE.md").read_text(encoding="utf-8")
            if (root / ".claude/CLAUDE.md").exists()
            else False
        ),
    }
    missing_rm = [k for k, v in rm_sources.items() if not v]
    if missing_rm:
        findings.append(
            {
                "id": "R-RUNNER-METRICS-DRIFT",
                "severity": "medium",
                "title": "runner.metrics ausente em fonte canonica",
                "evidence": {"missing_in": missing_rm},
                "recommendation": "Adicionar runner.metrics a todas as fontes do vocabulario reservado.",
            }
        )

    # M-05: prior_status enum drift entre contract YAML e schema JSON
    try:
        import yaml as _yaml

        ag_path = root / ".roadmap/AGENT_CONTRACT.yaml"
        sch_path = root / ".roadmap/agent_result.schema.json"
        if ag_path.exists() and sch_path.exists():
            ag = _yaml.safe_load(ag_path.read_text(encoding="utf-8")) or {}
            sch = json.loads(sch_path.read_text(encoding="utf-8"))
            yaml_allowed = set(
                ag.get("output_contract", {})
                .get("activity_event", {})
                .get("prior_status", {})
                .get("allowed_values", [])
            )
            schema_enum = set(
                sch.get("properties", {})
                .get("activity_event", {})
                .get("properties", {})
                .get("prior_status", {})
                .get("enum", [])
            )
            if yaml_allowed != schema_enum:
                findings.append(
                    {
                        "id": "R-PRIOR-STATUS-ENUM-DRIFT",
                        "severity": "medium",
                        "title": "prior_status enum diverge entre AGENT_CONTRACT.yaml e agent_result.schema.json",
                        "evidence": {
                            "yaml_allowed_values": sorted(yaml_allowed),
                            "schema_enum": sorted(schema_enum),
                            "only_in_yaml": sorted(yaml_allowed - schema_enum),
                            "only_in_schema": sorted(schema_enum - yaml_allowed),
                        },
                        "recommendation": "Alinhar AGENT_CONTRACT.yaml#prior_status.allowed_values com agent_result.schema.json enum.",
                    }
                )
    except Exception as exc:
        findings.append(
            {
                "id": "R-PRIOR-STATUS-CHECK-FAILED",
                "severity": "low",
                "title": "Falha ao executar check_prior_status_enum_drift",
                "evidence": {"error": str(exc)[:120]},
                "recommendation": "Verificar manualmente alinhamento entre AGENT_CONTRACT e agent_result.schema.",
            }
        )

    print(json.dumps({"checker": "contract_consistency", "findings": findings}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
