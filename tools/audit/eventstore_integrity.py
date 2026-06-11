#!/usr/bin/env python3
"""AUD-1201 â€” Integridade do event store e replay de projecao.

Checa monotonicidade/gaps de event_seq, append-only e reprodutibilidade das
projecoes por replay (em especial lessons.json). Read-only.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path


def parse_events(path: Path):
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    findings = []

    store = root / ".roadmap/activity.jsonl"
    if not store.exists():
        print(
            json.dumps(
                {
                    "checker": "eventstore_integrity",
                    "findings": [{"id": "ERR", "severity": "high", "title": "event store ausente"}],
                },
                indent=2,
            )
        )
        return 0
    events = parse_events(store)

    seqs = [e["event_seq"] for e in events]
    if seqs != sorted(seqs):
        findings.append(
            {
                "id": "R-order",
                "severity": "high",
                "title": "event_seq fora de ordem",
                "evidence": {"seqs": seqs},
            }
        )
    gaps = [i for i in range(1, len(seqs)) if seqs[i] != seqs[i - 1] + 1]
    if gaps:
        findings.append(
            {"id": "R-gap", "severity": "high", "title": "gaps em event_seq", "evidence": {"positions": gaps}}
        )

    # lessons reproducibility: lessons so nascem de issue.report(category=process,subtype=lesson)
    lesson_sources = [
        e
        for e in events
        if e["action"] == "issue.report"
        and e.get("payload", {}).get("category") == "process"
        and e.get("payload", {}).get("subtype") == "lesson"
    ]
    stored = root / ".roadmap/lessons.json"
    stored_lessons = (
        json.loads(stored.read_text(encoding="utf-8")).get("lessons", []) if stored.exists() else []
    )
    if stored_lessons and not lesson_sources:
        findings.append(
            {
                "id": "R1",
                "severity": "critical",
                "title": "lessons.json NAO e reconstruivel por replay",
                "evidence": {
                    "stored_lessons": [l["lesson_id"] for l in stored_lessons],
                    "lesson_creating_events": 0,
                },
                "recommendation": "Modelar lessons como eventos (issue.report/lesson) ou outra acao versionada; senao 'esaa project' apaga as lessons.",
            }
        )

    # schema_version misto nos eventos
    ev_versions = sorted({e.get("schema_version") for e in events})
    if len(ev_versions) > 1:
        findings.append(
            {
                "id": "R3b",
                "severity": "medium",
                "title": "schema_version misto no event store",
                "evidence": {"versions": ev_versions},
                "recommendation": "make_event usa constante fixa e regride eventos novos para a versao antiga.",
            }
        )

    print(
        json.dumps(
            {"checker": "eventstore_integrity", "events": len(events), "findings": findings},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
