#!/usr/bin/env python3
"""AUD-1814 — Critical findings audit checker.

Detects the architectural findings tracked by the critical-fixes trail:
- R-RUNNER-METRICS-DRIFT: runner.metrics missing in any canonical source
- R-NO-BASELINE-LESSON-RESEED: service.init not emitting baseline lessons event
- R-REVIEW-ROLE-DRIFT: projector forces owner-only review (no _reviewer_role check)
- R-NON-SERIALIZABLE-APPEND: append_transactional missing from store
- R-FILE-EFFECT-ARTIFACTS: file_effects module missing
- R-HOTFIX-VALIDATION: validate_hotfix_request missing
- R-DONE-PRIOR-STATUS: agent_result.schema prior_status enum lacks 'done'
- R-ATOMIC-FILE-EFFECTS: file_effects.stage_file_updates missing

Usage: python src/audit/critical_findings.py --root <repo_root>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


SERVICE_SOURCE_FILES = (
    "service.py",
    "service_core.py",
    "submission.py",
    "execution.py",
    "task_admin.py",
    "seeds.py",
    "events.py",
)


def _read_service_sources(root: Path) -> str:
    return "\n".join(_read(root / "src/esaa" / name) for name in SERVICE_SOURCE_FILES)


def _yaml_safe_load(p: Path):
    try:
        import yaml

        return yaml.safe_load(_read(p)) or {}
    except Exception:
        return {}


def check_runner_metrics(root: Path) -> list[dict]:
    findings = []
    sources = {
        "AGENT_CONTRACT.yaml": _yaml_safe_load(root / ".roadmap/AGENT_CONTRACT.yaml")
        .get("vocabulary", {})
        .get("reserved_orchestrator_actions", []),
        "ORCHESTRATOR_CONTRACT.yaml": _yaml_safe_load(root / ".roadmap/ORCHESTRATOR_CONTRACT.yaml")
        .get("roles", {})
        .get("orchestrator", {})
        .get("reserved_actions", []),
        "constants.py": "runner.metrics" in _read(root / "src/esaa/constants.py"),
    }
    missing = []
    for name, value in sources.items():
        if name == "constants.py":
            if not value:
                missing.append(name)
        else:
            if "runner.metrics" not in (value or []):
                missing.append(name)
    if missing:
        findings.append(
            {
                "id": "R-RUNNER-METRICS-DRIFT",
                "severity": "medium",
                "title": "runner.metrics missing from canonical sources",
                "evidence": {"missing_in": missing},
                "recommendation": "Add runner.metrics to all reserved-action vocabularies.",
            }
        )
    return findings


def check_baseline_lessons_reseed(root: Path) -> list[dict]:
    src = _read_service_sources(root)
    findings = []
    if "BASELINE_LESSONS" not in src:
        findings.append(
            {
                "id": "R-NO-BASELINE-LESSON-RESEED",
                "severity": "high",
                "title": "service modules lack BASELINE_LESSONS constant",
                "evidence": {"files": [f"src/esaa/{name}" for name in SERVICE_SOURCE_FILES]},
                "recommendation": "Define BASELINE_LESSONS and emit baseline_reseed event in init.",
            }
        )
    elif "baseline_reseed" not in src:
        findings.append(
            {
                "id": "R-NO-BASELINE-LESSON-RESEED",
                "severity": "high",
                "title": "service.init not emitting baseline_reseed event",
                "evidence": {
                    "files": [f"src/esaa/{name}" for name in SERVICE_SOURCE_FILES],
                    "missing_marker": "baseline_reseed",
                },
                "recommendation": "Append orchestrator.view.mutate with baseline_reseed in init.",
            }
        )
    return findings


def check_review_role(root: Path) -> list[dict]:
    src = _read(root / "src/esaa/projector.py")
    findings = []
    if "_reviewer_role" not in src:
        findings.append(
            {
                "id": "R-REVIEW-ROLE-DRIFT",
                "severity": "high",
                "title": "projector._apply_review missing role-based authorization",
                "evidence": {"file": "src/esaa/projector.py"},
                "recommendation": "Honor _reviewer_role in payload to allow qa_role mode.",
            }
        )
    return findings


def check_serializable_append(root: Path) -> list[dict]:
    src = _read(root / "src/esaa/store.py")
    findings = []
    if "append_transactional" not in src:
        findings.append(
            {
                "id": "R-NON-SERIALIZABLE-APPEND",
                "severity": "critical",
                "title": "store.append_transactional missing",
                "evidence": {"file": "src/esaa/store.py"},
                "recommendation": "Add lock-then-revalidate-then-write transactional API.",
            }
        )
    return findings


def check_file_effects_module(root: Path) -> list[dict]:
    p = root / "src/esaa/file_effects.py"
    findings = []
    if not p.exists():
        findings.append(
            {
                "id": "R-FILE-EFFECT-ARTIFACTS",
                "severity": "high",
                "title": "src/esaa/file_effects.py missing",
                "evidence": {"expected_file": "src/esaa/file_effects.py"},
                "recommendation": "Implement staging + content-addressed artifacts.",
            }
        )
        return findings
    src = _read(p)
    required = [
        "stage_file_updates",
        "commit_staged",
        "discard_staged",
        "compute_file_metadata",
        "write_artifact",
        "verify_artifact",
        "read_artifact",
        "recover_file_effects",
    ]
    missing = [s for s in required if s not in src]
    if missing:
        findings.append(
            {
                "id": "R-FILE-EFFECT-ARTIFACTS",
                "severity": "medium",
                "title": "file_effects.py missing required functions",
                "evidence": {"missing": missing},
                "recommendation": "Implement: " + ", ".join(missing),
            }
        )
    return findings


def check_hotfix_validation(root: Path) -> list[dict]:
    src = _read_service_sources(root)
    findings = []
    if "validate_hotfix_request" not in src:
        findings.append(
            {
                "id": "R-HOTFIX-VALIDATION",
                "severity": "medium",
                "title": "service hotfix validation missing",
                "evidence": {"files": [f"src/esaa/{name}" for name in SERVICE_SOURCE_FILES]},
                "recommendation": "Add validate_hotfix_request returning structured codes.",
            }
        )
        return findings
    expected_codes = [
        "HOTFIX_ISSUE_NOT_FOUND",
        "HOTFIX_TARGET_NOT_FOUND",
        "HOTFIX_TARGET_NOT_DONE",
        "HOTFIX_SCOPE_INVALID",
    ]
    missing = [c for c in expected_codes if c not in src]
    if missing:
        findings.append(
            {
                "id": "R-HOTFIX-VALIDATION",
                "severity": "low",
                "title": "validate_hotfix_request missing error codes",
                "evidence": {"missing_codes": missing},
                "recommendation": "Emit all hotfix structured reject codes.",
            }
        )
    return findings


def check_done_in_prior_status(root: Path) -> list[dict]:
    p = root / ".roadmap/agent_result.schema.json"
    findings = []
    if not p.exists():
        return findings
    data = json.loads(_read(p))
    enum = (
        data.get("properties", {})
        .get("activity_event", {})
        .get("properties", {})
        .get("prior_status", {})
        .get("enum", [])
    )
    if "done" not in enum:
        findings.append(
            {
                "id": "R-DONE-PRIOR-STATUS",
                "severity": "high",
                "title": "agent_result.schema prior_status enum lacks 'done'",
                "evidence": {"current_enum": enum},
                "recommendation": "Add 'done' to enable issue.report on done tasks.",
            }
        )
    return findings


def check_plugin_dispatch_parity(root: Path) -> list[dict]:
    src = _read_service_sources(root)
    findings = []
    required = ["tasks_with_planned_plugins", "_accept_agent_output", "task.create"]
    missing = [marker for marker in required if marker not in src]
    if missing:
        findings.append(
            {
                "id": "R-PLUGIN-DISPATCH-DRIFT",
                "severity": "high",
                "title": "run path no longer appears to consume planned plugin tasks",
                "evidence": {
                    "missing_markers": missing,
                    "files": [f"src/esaa/{name}" for name in SERVICE_SOURCE_FILES],
                },
                "recommendation": "Keep run/eligible on the same tasks_with_planned_plugins view and admit task.create before claim.",
            }
        )
    return findings


def check_dry_run_semantics(root: Path) -> list[dict]:
    src = _read_service_sources(root)
    findings = []
    required = ['"status": "dry_run"', "would_append_events", "simulated_last_event_seq"]
    missing = [marker for marker in required if marker not in src]
    if missing:
        findings.append(
            {
                "id": "R-DRY-RUN-AMBIGUOUS",
                "severity": "medium",
                "title": "dry-run responses may be ambiguous",
                "evidence": {
                    "missing_markers": missing,
                    "files": [f"src/esaa/{name}" for name in SERVICE_SOURCE_FILES],
                },
                "recommendation": "Return status=dry_run and simulated append metadata for every dry-run command.",
            }
        )
    return findings


CHECKS = [
    ("runner_metrics", check_runner_metrics),
    ("baseline_lessons_reseed", check_baseline_lessons_reseed),
    ("review_role", check_review_role),
    ("serializable_append", check_serializable_append),
    ("file_effects_module", check_file_effects_module),
    ("hotfix_validation", check_hotfix_validation),
    ("done_in_prior_status", check_done_in_prior_status),
    ("plugin_dispatch_parity", check_plugin_dispatch_parity),
    ("dry_run_semantics", check_dry_run_semantics),
]


def run_checks(root: Path) -> dict:
    all_findings = []
    by_check = {}
    for name, fn in CHECKS:
        result = fn(root)
        by_check[name] = len(result)
        all_findings.extend(result)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity"), 9))
    return {
        "checker": "critical_findings",
        "total_findings": len(all_findings),
        "by_check": by_check,
        "by_severity": {
            sev: sum(1 for f in all_findings if f.get("severity") == sev) for sev in severity_order
        },
        "findings": all_findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    result = run_checks(Path(args.root))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["total_findings"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
