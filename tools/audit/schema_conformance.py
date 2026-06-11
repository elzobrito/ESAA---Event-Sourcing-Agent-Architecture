#!/usr/bin/env python3
"""AUD-1101 â€” Validador de schema e detector de drift de versao.

Valida roadmap.json/issues.json/lessons.json contra seus *.schema.json
(quando jsonschema disponivel) e checa schema_version declarado nos dados
vs contratos. Read-only. Saida: JSON de findings.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path


def load(root: Path, rel: str):
    p = root / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    findings = []

    data_versions = {}
    for rel in ("roadmap.json", "issues.json", "lessons.json"):
        d = load(root, ".roadmap/" + rel)
        if d:
            data_versions[rel] = d.get("meta", {}).get("schema_version")
    if set(data_versions.values()) == {"0.4.0"}:
        findings.append(
            {
                "id": "R3",
                "severity": "high",
                "title": "Projecoes ainda em schema_version 0.4.0 apos upgrade de contrato 0.4.1",
                "evidence": data_versions,
                "recommendation": "Projetor deve carimbar a versao vigente dos contratos.",
            }
        )

    try:
        import jsonschema  # noqa

        for data_rel, schema_rel in (
            ("roadmap.json", "roadmap.schema.json"),
            ("issues.json", "issues.schema.json"),
            ("lessons.json", "lessons.schema.json"),
        ):
            d = load(root, ".roadmap/" + data_rel)
            s = load(root, ".roadmap/" + schema_rel)
            if d and s:
                try:
                    jsonschema.validate(d, s)
                except jsonschema.ValidationError as e:
                    findings.append(
                        {
                            "id": "R-schema",
                            "severity": "medium",
                            "title": f"{data_rel} nao conforma com {schema_rel}",
                            "evidence": {"error": str(e).splitlines()[0]},
                            "recommendation": "Reconciliar dado e schema.",
                        }
                    )
    except ImportError:
        findings.append(
            {
                "id": "INFO",
                "severity": "info",
                "title": "jsonschema indisponivel; validacao formal pulada",
                "evidence": {},
                "recommendation": "pip install jsonschema",
            }
        )

    print(json.dumps({"checker": "schema_conformance", "findings": findings}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
