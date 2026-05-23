"""FIX-1805 / FIX-1808 â€” Atomic file effects + content-addressed artifacts.



API:

- stage_file_updates(root, file_updates) -> staged list

- commit_staged(staged)                  -> apply to final paths

- discard_staged(staged)                 -> cleanup on failure

- cleanup_orphan_staging(root)           -> sweep abandoned staged files

- compute_file_metadata(root, path, content) -> {before/after sha256, bytes, encoding}

- write_artifact(root, metadata, content) -> artifact_path (content-addressed)

- verify_artifact(root, artifact_path)   -> bool, mismatch details

"""

from __future__ import annotations



import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone

from pathlib import Path

from typing import Any





STAGING_DIR = ".roadmap/staging"

ARTIFACT_DIR = ".roadmap/artifacts/file-effects"





def _utc_now_iso() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")





def _sha256_bytes(data: bytes) -> str:

    return hashlib.sha256(data).hexdigest()





def stage_file_updates(root: Path, file_updates: list[dict[str, str]]) -> list[dict[str, Any]]:

    """Stage file_updates em .roadmap/staging/. Returns list of staged records."""

    staging_root = root / STAGING_DIR

    staging_root.mkdir(parents=True, exist_ok=True)

    staged: list[dict[str, Any]] = []
    for i, item in enumerate(file_updates):
        final_path = item["path"].replace("\\", "/")
        content = item["content"]
        # Use hash-based staging name to avoid collisions
        staged_name = f"stage-{i:04d}-{_sha256_bytes(content.encode('utf-8'))[:12]}.tmp"
        staged_path = staging_root / staged_name
        staged_path.write_text(content, encoding="utf-8")
        staged.append({
            "final_path": final_path,
            "staged_path": str(staged_path),
            "content": content,
        })
    return staged





def commit_staged(root: Path, staged: list[dict[str, Any]]) -> None:
    """Apply staged files atomically to final paths."""
    for entry in staged:
        final = root / entry["final_path"]
        staged_p = Path(entry["staged_path"])
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_p, final)




def discard_staged(staged: list[dict[str, Any]]) -> None:

    """Cleanup staged files on failure."""

    for entry in staged:

        try:

            Path(entry["staged_path"]).unlink()

        except FileNotFoundError:

            pass





def cleanup_orphan_staging(root: Path) -> int:

    """Remove arquivos staged abandonados. Returns count removed."""

    staging_root = root / STAGING_DIR

    if not staging_root.exists():

        return 0

    n = 0

    for p in staging_root.glob("stage-*.tmp"):

        try:

            p.unlink()

            n += 1

        except OSError:

            pass

    return n





def compute_file_metadata(root: Path, path: str, after_content: str,

                          encoding: str = "utf-8") -> dict[str, Any]:

    """Computa metadados de auditoria para um file_update."""

    final = root / path

    if final.exists():

        before = final.read_bytes()

        before_sha = _sha256_bytes(before)

    else:

        before_sha = None

    after_bytes = after_content.encode(encoding)

    return {

        "path": path,

        "before_sha256": before_sha,

        "after_sha256": _sha256_bytes(after_bytes),

        "bytes": len(after_bytes),

        "encoding": encoding,

    }





def _canonical_artifact_hash(payload: dict[str, Any]) -> str:

    """Hash determinÃ­stico do payload SEM o prÃ³prio artifact_sha256."""

    p = {k: v for k, v in payload.items() if k != "artifact_sha256"}

    canon = json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    return _sha256_bytes(canon.encode("utf-8"))





def write_artifact(root: Path, metadata: dict[str, Any], content: str) -> dict[str, Any]:

    """Grava artifact content-addressed e devolve metadata atualizada com

    artifact_sha256 e artifact_path."""

    artifact_root = root / ARTIFACT_DIR

    artifact_root.mkdir(parents=True, exist_ok=True)

    payload = {

        "artifact_id": f"ART-{metadata['after_sha256']}",

        "path": metadata["path"],

        "before_sha256": metadata.get("before_sha256"),

        "after_sha256": metadata["after_sha256"],

        "bytes": metadata["bytes"],

        "encoding": metadata.get("encoding", "utf-8"),

        "content": content,

        "ts": _utc_now_iso(),

    }

    artifact_sha = _canonical_artifact_hash(payload)

    payload["artifact_sha256"] = artifact_sha

    artifact_filename = f"{artifact_sha}.json"

    artifact_path = artifact_root / artifact_filename

    if not artifact_path.exists():

        artifact_path.write_text(

            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",

            encoding="utf-8",

        )

    out = dict(metadata)

    out["artifact_sha256"] = artifact_sha

    out["artifact_path"] = f"{ARTIFACT_DIR}/{artifact_filename}"

    return out





def verify_artifact(root: Path, artifact_path: str) -> tuple[bool, str | None]:

    """Verifica que o artifact existe e tem hash consistente.

    Returns (ok, error_code|None).

    """

    p = root / artifact_path

    if not p.exists():

        return False, "ARTIFACT_MISSING"

    try:

        data = json.loads(p.read_text(encoding="utf-8"))

    except json.JSONDecodeError:

        return False, "ARTIFACT_INVALID_JSON"

    declared = data.get("artifact_sha256")

    if not declared:

        return False, "ARTIFACT_NO_HASH"

    computed = _canonical_artifact_hash(data)

    if computed != declared:

        return False, "ARTIFACT_HASH_MISMATCH"

    # Reconfere after_sha256 do content

    content = data.get("content", "")

    enc = data.get("encoding", "utf-8")

    if _sha256_bytes(content.encode(enc)) != data.get("after_sha256"):

        return False, "ARTIFACT_CONTENT_HASH_MISMATCH"

    return True, None


def read_artifact(root: Path, artifact_path: str) -> dict[str, Any]:
    ok, error = verify_artifact(root, artifact_path)
    if not ok:
        raise ValueError(error or "ARTIFACT_INVALID")
    return json.loads((root / artifact_path).read_text(encoding="utf-8"))


def _safe_rel_path(path: str) -> str:
    norm = path.replace("\\", "/").strip()
    parts = [part for part in norm.split("/") if part]
    if not norm or norm.startswith("/") or any(part == ".." for part in parts):
        raise ValueError(f"unsafe artifact path: {path}")
    return "/".join(parts)


def recover_file_effects(root: Path, events: list[dict[str, Any]], dry_run: bool = False) -> dict[str, Any]:
    latest_by_path: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("action") != "orchestrator.file.write":
            continue
        for effect in event.get("payload", {}).get("effects", []) or []:
            path = effect.get("path")
            if path and effect.get("artifact_path"):
                latest_by_path[path] = effect

    recovered: list[str] = []
    already_applied: list[str] = []
    errors: list[dict[str, str]] = []

    for path, effect in sorted(latest_by_path.items()):
        try:
            artifact = read_artifact(root, effect["artifact_path"])
            rel_path = _safe_rel_path(artifact["path"])
            final = root / rel_path
            after_sha = artifact["after_sha256"]
            if final.exists() and _sha256_bytes(final.read_bytes()) == after_sha:
                already_applied.append(rel_path)
                continue
            if not dry_run:
                final.parent.mkdir(parents=True, exist_ok=True)
                final.write_bytes(artifact.get("content", "").encode(artifact.get("encoding", "utf-8")))
            recovered.append(rel_path)
        except Exception as exc:
            errors.append({"path": path, "error": str(exc)})

    return {
        "status": "dry_run" if dry_run else "recovered",
        "files_recovered": len(recovered),
        "files_already_applied": len(already_applied),
        "errors": errors,
        "recovered": recovered,
        "already_applied": already_applied,
    }




def stage_and_compute(root: Path, file_updates: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

    """Atomico: stage + compute metadata + write_artifact em uma chamada.

    Returns (staged_list, metadata_list).

    """

    staged = stage_file_updates(root, file_updates)

    metadata_list: list[dict[str, Any]] = []

    for entry in staged:

        meta = compute_file_metadata(root, entry["final_path"], entry["content"])

        meta = write_artifact(root, meta, entry["content"])

        metadata_list.append(meta)

    return staged, metadata_list

