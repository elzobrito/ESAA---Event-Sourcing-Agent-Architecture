"""G08 (PROV-01) — resolucao do bloco runner pelo single writer.

O agente nunca envia `runner`; o Orchestrator resolve e carimba o bloco em
`make_event()` no momento do append. Precedencia: CLI --runner (exportado em
ESAA_RUNNER_ID pelo cli.main) > variavel de ambiente > DEFAULT_RUNNER_ID.
"""

from __future__ import annotations

import os
from typing import Any

from .errors import ESAAError

DEFAULT_RUNNER_ID = "unattended"
ENV_RUNNER_ID = "ESAA_RUNNER_ID"
ENV_RUNNER_KIND = "ESAA_RUNNER_KIND"
ENV_COMMAND_SURFACE = "ESAA_COMMAND_SURFACE"
ENV_ON_BEHALF_OF = "ESAA_ON_BEHALF_OF"


def _optional_env(name: str, default: str | None = None) -> str | None:
    value = (os.environ.get(name) or "").strip()
    return value or default


def resolve_runner() -> dict[str, Any]:
    """Resolve o bloco runner a partir do ambiente do processo."""
    return {
        "runner_id": _optional_env(ENV_RUNNER_ID, DEFAULT_RUNNER_ID),
        "runner_kind": _optional_env(ENV_RUNNER_KIND),
        "command_surface": _optional_env(ENV_COMMAND_SURFACE, "cli"),
        "on_behalf_of": _optional_env(ENV_ON_BEHALF_OF),
    }


def validate_runner_block(runner: Any) -> None:
    """Fail-closed: bloco presente deve ter runner_id string nao-vazia."""
    if (
        not isinstance(runner, dict)
        or not isinstance(runner.get("runner_id"), str)
        or not runner["runner_id"].strip()
    ):
        raise ESAAError("RUNNER_INVALID", "runner block must be an object with non-empty runner_id")
