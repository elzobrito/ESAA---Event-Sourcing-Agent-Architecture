from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tomllib
from importlib import resources
from pathlib import Path

import yaml

from esaa.bootstrap import GOVERNANCE_TEMPLATE_FILES, bootstrap_workspace
from esaa.cli import main
from esaa.errors import ESAAError
from esaa.service import ESAAService


def _run_cli(root: Path, *args: str) -> dict:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = main(["--root", str(root), *args])
    assert code == 0, stdout.getvalue()
    return json.loads(stdout.getvalue())


def test_bootstrap_creates_required_governance_files(tmp_path: Path) -> None:
    result = bootstrap_workspace(tmp_path, profile="public")

    assert result["status"] == "bootstrapped"
    assert result["profile"] == "public"
    assert sorted(result["files_written"]) == sorted(f".roadmap/{name}" for name in GOVERNANCE_TEMPLATE_FILES)
    for name in GOVERNANCE_TEMPLATE_FILES:
        assert (tmp_path / ".roadmap" / name).exists()

    assert not (tmp_path / ".roadmap" / "activity.jsonl").exists()
    assert not (tmp_path / ".roadmap" / "roadmap.json").exists()
    assert not (tmp_path / ".roadmap" / "issues.json").exists()
    assert not (tmp_path / ".roadmap" / "lessons.json").exists()


def test_bootstrap_refuses_existing_files_without_force(tmp_path: Path) -> None:
    bootstrap_workspace(tmp_path, profile="public")

    with pytest_raises_esaa("BOOTSTRAP_TARGET_EXISTS"):
        bootstrap_workspace(tmp_path, profile="public")


def test_bootstrap_never_overwrites_event_store_or_read_models(tmp_path: Path) -> None:
    roadmap = tmp_path / ".roadmap"
    roadmap.mkdir()
    protected = {
        "activity.jsonl": "event-store\n",
        "roadmap.json": '{"protected":"roadmap"}\n',
        "issues.json": '{"protected":"issues"}\n',
        "lessons.json": '{"protected":"lessons"}\n',
    }
    for name, content in protected.items():
        (roadmap / name).write_text(content, encoding="utf-8")

    bootstrap_workspace(tmp_path, profile="production", force=True)

    for name, content in protected.items():
        assert (roadmap / name).read_text(encoding="utf-8") == content


def test_bootstrap_force_only_overwrites_allowlisted_governance_files(tmp_path: Path) -> None:
    bootstrap_workspace(tmp_path, profile="public")
    target = tmp_path / ".roadmap" / "AGENT_CONTRACT.yaml"
    target.write_text("broken: true\n", encoding="utf-8")

    result = bootstrap_workspace(tmp_path, profile="production", force=True)

    assert ".roadmap/AGENT_CONTRACT.yaml" in result["files_written"]
    assert "allowed_agent_actions" in target.read_text(encoding="utf-8")
    policy = yaml.safe_load((tmp_path / ".roadmap" / "RUNTIME_POLICY.yaml").read_text(encoding="utf-8"))
    assert policy["review_authorization"] == "qa_role"


def test_bootstrap_cli_then_init_verify_and_eligible(tmp_path: Path) -> None:
    bootstrap_result = _run_cli(tmp_path, "bootstrap", "--profile", "public")
    assert bootstrap_result["status"] == "bootstrapped"

    init_result = _run_cli(tmp_path, "init")
    assert init_result["last_event_seq"] > 0

    verify_result = _run_cli(tmp_path, "verify")
    assert verify_result["verify_status"] == "ok"

    eligible_result = _run_cli(tmp_path, "eligible")
    assert eligible_result["eligible_count"] >= 1


def test_package_data_contains_templates() -> None:
    template_root = resources.files("esaa").joinpath("templates")
    assert all(template_root.joinpath(name).is_file() for name in GOVERNANCE_TEMPLATE_FILES)


def test_pyproject_public_metadata(repo_root: Path) -> None:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]

    assert project["version"] == "0.5.0b1"
    assert project["license"]["text"] == "MIT"
    assert project["authors"] == [{"name": "ESAA Contributors"}]
    assert project["urls"]["Homepage"] == "https://github.com/elzobrito/ESAA---Event-Sourcing-Agent-Architecture"
    assert "build>=1.2.0" in project["optional-dependencies"]["dev"]
    assert "twine>=5.1.0" in project["optional-dependencies"]["dev"]


def test_bootstrap_installed_console_smoke(tmp_path: Path, repo_root: Path) -> None:
    if not (repo_root / "dist").exists():
        return
    wheels = sorted((repo_root / "dist").glob("esaa_core-0.5.0b1-*.whl"))
    if not wheels:
        return

    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    esaa = venv_dir / ("Scripts/esaa.exe" if sys.platform == "win32" else "bin/esaa")
    subprocess.run([str(python), "-m", "pip", "install", "--force-reinstall", str(wheels[-1])], check=True)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run([str(esaa), "--root", str(workspace), "bootstrap", "--profile", "public"], check=True)
    subprocess.run([str(esaa), "--root", str(workspace), "init"], check=True)
    verify = subprocess.run([str(esaa), "--root", str(workspace), "verify"], check=True, capture_output=True, text=True)
    assert '"verify_status": "ok"' in verify.stdout


class pytest_raises_esaa:
    def __init__(self, code: str) -> None:
        self.code = code

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert exc_type is ESAAError
        assert exc.code == self.code
        return True
