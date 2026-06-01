from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from .errors import ESAAError


GOVERNANCE_TEMPLATE_FILES = (
    "AGENT_CONTRACT.yaml",
    "ORCHESTRATOR_CONTRACT.yaml",
    "RUNTIME_POLICY.yaml",
    "STORAGE_POLICY.yaml",
    "PROJECTION_SPEC.md",
    "agent_result.schema.json",
    "roadmap.schema.json",
    "issues.schema.json",
    "lessons.schema.json",
    "agents_swarm.yaml",
    "PARCER_PROFILE.agent-docs.yaml",
    "PARCER_PROFILE.agent-spec.yaml",
    "PARCER_PROFILE.agent-impl.yaml",
    "PARCER_PROFILE.agent-qa.yaml",
    "PARCER_PROFILE.orchestrator-runtime.yaml",
)

PROFILES = {"public", "production"}

PROTECTED_RELATIVE_PATHS = {
    ".roadmap/activity.jsonl",
    ".roadmap/roadmap.json",
    ".roadmap/issues.json",
    ".roadmap/lessons.json",
    ".roadmap/artifacts",
    ".roadmap/backups",
    ".roadmap/snapshots",
}


def _template_bytes(name: str) -> bytes:
    template = resources.files("esaa").joinpath("templates", name)
    return template.read_bytes()


def bootstrap_workspace(root: Path, profile: str = "public", force: bool = False) -> dict[str, Any]:
    """Copy packaged ESAA governance templates into a workspace.

    Bootstrap installs the public governance bundle: contracts, schemas,
    runtime/storage policy, projection spec, and PARCER profiles. Event stores
    and materialized read models stay untouched so a public package can safely
    prepare existing workspaces.
    """
    if profile not in PROFILES:
        raise ESAAError("BOOTSTRAP_PROFILE_INVALID", f"profile must be one of {sorted(PROFILES)}")

    root = Path(root)
    roadmap_dir = root / ".roadmap"
    roadmap_dir.mkdir(parents=True, exist_ok=True)

    targets = [(name, roadmap_dir / name) for name in GOVERNANCE_TEMPLATE_FILES]
    existing = [f".roadmap/{name}" for name, path in targets if path.exists()]
    if existing and not force:
        raise ESAAError(
            "BOOTSTRAP_TARGET_EXISTS",
            "governance files already exist; use --force to overwrite allowlisted files",
        )

    files_written: list[str] = []
    for name, path in targets:
        path.write_bytes(_template_bytes(name))
        files_written.append(f".roadmap/{name}")

    return {
        "status": "bootstrapped",
        "profile": profile,
        "force": force,
        "files_written": files_written,
        "protected_paths": sorted(PROTECTED_RELATIVE_PATHS),
    }
