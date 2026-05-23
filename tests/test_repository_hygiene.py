from __future__ import annotations

from pathlib import Path


def test_gitignore_keeps_canonical_esaa_files_tracked(repo_root: Path) -> None:
    text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert ".roadmap/activity.jsonl" not in text
    assert ".roadmap/roadmap.json" not in text
    assert ".roadmap/backups/" in text
    assert "*.lock" in text


def test_repository_hygiene_doc_exists(repo_root: Path) -> None:
    doc = repo_root / "docs/operations/repository-hygiene.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "Never ignore `.roadmap/activity.jsonl`" in text
