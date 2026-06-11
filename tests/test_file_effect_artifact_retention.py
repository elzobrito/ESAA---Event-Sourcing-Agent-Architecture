from __future__ import annotations

from pathlib import Path

from test_file_effect_recovery import test_file_effect_recovery_flow as _recovery

from esaa.file_effects import discard_staged, read_artifact, stage_and_compute, verify_artifact


def test_file_effect_artifact_recovery_flow(contract_bundle: Path, monkeypatch) -> None:
    _recovery(contract_bundle, monkeypatch)


def test_file_effect_artifact_can_be_read(contract_bundle: Path) -> None:
    staged, effects = stage_and_compute(
        contract_bundle,
        [{"path": "docs/spec/artifact-retention.md", "content": "artifact retained\n"}],
    )
    try:
        artifact_path = effects[0]["artifact_path"]
        data = read_artifact(contract_bundle, artifact_path)
        assert data["content"] == "artifact retained\n"
        assert verify_artifact(contract_bundle, artifact_path) == (True, None)
    finally:
        discard_staged(staged)
