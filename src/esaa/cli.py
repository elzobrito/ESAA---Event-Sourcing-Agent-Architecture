from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import ESAAError
from .service import ESAAService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esaa", description="ESAA deterministic orchestrator core")
    parser.add_argument("--root", default=".", help="project root path")

    sub = parser.add_subparsers(dest="command", required=True)

    cmd_init = sub.add_parser("init", help="initialize canonical clean-state")
    cmd_init.add_argument("--run-id", default="RUN-0001")
    cmd_init.add_argument("--master-correlation-id", default="CID-ESAA-INIT")
    cmd_init.add_argument("--force", action="store_true")

    cmd_run = sub.add_parser("run", help="execute orchestration steps (mock adapter)")
    cmd_run.add_argument("--steps", type=int, default=1)
    cmd_run.add_argument("--dry-run", action="store_true")

    cmd_submit = sub.add_parser("submit", help="validate and apply an agent.result JSON")
    cmd_submit.add_argument("file", nargs="?", default="-", help="path to agent.result JSON file (default: stdin)")
    cmd_submit.add_argument("--actor", required=True, help="agent identity (e.g. agent-spec, claude-code)")
    cmd_submit.add_argument("--dry-run", action="store_true", help="validate without persisting")

    cmd_process = sub.add_parser("process", help="process all pending files from .roadmap/inbox/")
    cmd_process.add_argument("--dry-run", action="store_true", help="validate without persisting or moving files")

    sub.add_parser("project", help="reproject read-models from event store")
    sub.add_parser("verify", help="verify projection consistency")

    cmd_replay = sub.add_parser("replay", help="rebuild state until event id/seq")
    cmd_replay.add_argument("--until", default=None, help="event_seq (number) or event_id")
    cmd_replay.add_argument("--no-write", action="store_true", help="compute replay without writing views")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    service = ESAAService(root=root)

    try:
        if args.command == "init":
            result = service.init(
                run_id=args.run_id,
                master_correlation_id=args.master_correlation_id,
                force=args.force,
            )
        elif args.command == "run":
            result = service.run(steps=args.steps, dry_run=args.dry_run)
        elif args.command == "submit":
            if args.file == "-":
                raw = sys.stdin.read()
            else:
                raw = Path(args.file).read_text(encoding="utf-8")
            agent_output = json.loads(raw)
            result = service.submit(agent_output, actor=args.actor, dry_run=args.dry_run)
        elif args.command == "process":
            result = service.process(dry_run=args.dry_run)
        elif args.command == "project":
            result = service.project()
        elif args.command == "verify":
            result = service.verify()
        elif args.command == "replay":
            result = service.replay(until=args.until, write_views=not args.no_write)
        else:
            raise ESAAError("UNKNOWN_COMMAND", f"unknown command: {args.command}")

        print(json.dumps(result, ensure_ascii=False, indent=2))
        verify_status = result.get("verify_status")
        if verify_status in {"mismatch", "corrupted"}:
            return 2
        return 0
    except ESAAError as exc:
        print(
            json.dumps(
                {"error_code": exc.code, "error_message": exc.message},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
