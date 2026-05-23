from __future__ import annotations

from pathlib import Path

from esaa.file_effects import read_artifact, verify_artifact
from test_file_effect_recovery import test_file_effect_recovery_flow as _recovery


def test_file_effect_artifact_recovery_flow(contract_bundle: Path, monkeypatch) -> None:
    _recovery(contract_bundle, monkeypatch)


def test_file_effect_artifact_can_be_read(repo_root: Path) -> None:
    artifact_dir = repo_root / ".roadmap/artifacts/file-effects"
    artifacts = sorted(artifact_dir.glob("*.json"))
    assert artifacts
    data = read_artifact(repo_root, str(artifacts[0].relative_to(repo_root)).replace("\\", "/"))
    assert "content" in data
    assert verify_artifact(repo_root, str(artifacts[0].relative_to(repo_root)).replace("\\", "/"))
