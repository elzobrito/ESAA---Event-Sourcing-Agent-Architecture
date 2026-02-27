from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def contract_bundle(tmp_path: Path, repo_root: Path) -> Path:
    source = repo_root / ".roadmap"
    target = tmp_path / ".roadmap"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("AGENT_CONTRACT.yaml", "agent_result.schema.json"):
        shutil.copy2(source / name, target / name)
    return tmp_path

