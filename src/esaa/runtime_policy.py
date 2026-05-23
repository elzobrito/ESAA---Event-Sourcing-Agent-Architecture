"""Attempt lifecycle (R2) — RF aplicada localmente pelo Orchestrator.

Le RUNTIME_POLICY.yaml e consulta o event store para decidir:
- esta tarefa atingiu max_attempts? (output.rejected events penalizantes)
- esta tarefa em cooldown? (rejeicao recente nas ultimas N segundos)
- esta tarefa em attempt expirado? (claim sem complete ha mais que TTL)

Sem estado em memoria: tudo derivavel do event store (event-sourced).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_POLICY = {
    "attempt_lifecycle": {"ttl": "PT30M"},
    "attempt_limits": {
        "max_attempts_per_task": 3,
        "cooldown_between_attempts": "PT2M",
    },
}


def load_policy(root: Path) -> dict[str, Any]:
    path = root / ".roadmap" / "RUNTIME_POLICY.yaml"
    if not path.exists():
        return DEFAULT_POLICY
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


_ISO_DUR = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def parse_duration(s: str) -> timedelta:
    """ISO-8601 duration limitada a PT<H>H<M>M<S>S."""
    m = _ISO_DUR.match(s.strip())
    if not m:
        return timedelta(0)
    h, mn, sec = (int(x) if x else 0 for x in m.groups())
    return timedelta(hours=h, minutes=mn, seconds=sec)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def count_penalizing_rejections(events: list[dict[str, Any]], task_id: str) -> int:
    """Conta output.rejected events para a tarefa onde penalizes_counter != False.

    Por compatibilidade, o payload nao traz penalizes_counter; o codigo
    PRIOR_STATUS_MISMATCH e o unico nao-penalizante (per contract).
    """
    n = 0
    for e in events:
        if e.get("action") != "output.rejected":
            continue
        p = e.get("payload") or {}
        if p.get("task_id") != task_id:
            continue
        if p.get("error_code") == "PRIOR_STATUS_MISMATCH":
            continue
        n += 1
    return n


def last_rejection_ts(events: list[dict[str, Any]], task_id: str) -> datetime | None:
    last = None
    for e in events:
        if e.get("action") != "output.rejected":
            continue
        p = e.get("payload") or {}
        if p.get("task_id") != task_id:
            continue
        try:
            last = _parse_ts(e["ts"])
        except Exception:
            continue
    return last


def is_in_cooldown(events: list[dict[str, Any]], task_id: str, now: datetime, cooldown: timedelta) -> bool:
    ts = last_rejection_ts(events, task_id)
    if ts is None:
        return False
    return (now - ts) < cooldown


def is_blocked_by_max_attempts(events: list[dict[str, Any]], task_id: str, max_attempts: int) -> bool:
    return count_penalizing_rejections(events, task_id) >= max_attempts


def resolve_role(actor: str, root: Path | None = None) -> str:
    """FIX-1807 — Resolve role de um actor.

    Consulta .roadmap/agents_swarm.yaml se existir: agents[<actor>].role.
    Fallback heuristico: prefixo 'agent-qa*' -> 'qa'; 'agent-orchestrator*' -> 'orchestrator';
    outros -> 'agent'.
    """
    if root is not None:
        swarm_path = root / ".roadmap" / "agents_swarm.yaml"
        if swarm_path.exists():
            try:
                data = yaml.safe_load(swarm_path.read_text(encoding="utf-8")) or {}
                role = (data.get("agents", {}).get(actor, {}) or {}).get("role")
                if role:
                    role_value = str(role)
                    return "qa" if role_value == "quality" else role_value
            except Exception:
                pass
    if actor.startswith("agent-qa"):
        return "qa"
    if actor.startswith("agent-orchestrator") or actor == "orchestrator":
        return "orchestrator"
    return "agent"


def review_authorization_mode(policy: dict[str, Any]) -> str:
    """FIX-1807 — modo de autorizacao para review: 'owner' (legado) ou 'qa_role'."""
    val = policy.get("review_authorization", "owner")
    return val if val in {"owner", "qa_role"} else "owner"


def attempt_expired(events: list[dict[str, Any]], task_id: str, now: datetime, ttl: timedelta) -> bool:
    """Tarefa em in_progress sem complete ha mais que ttl?"""
    last_claim = None
    last_complete = None
    for e in events:
        p = e.get("payload") or {}
        if p.get("task_id") != task_id:
            continue
        act = e.get("action")
        if act == "claim":
            try:
                last_claim = _parse_ts(e["ts"])
            except Exception:
                pass
        elif act == "complete":
            try:
                last_complete = _parse_ts(e["ts"])
            except Exception:
                pass
    if last_claim is None:
        return False
    if last_complete is not None and last_complete >= last_claim:
        return False
    return (now - last_claim) > ttl
