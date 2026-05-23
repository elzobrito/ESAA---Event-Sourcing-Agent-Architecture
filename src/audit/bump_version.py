#!/usr/bin/env python3
"""FIX-1551 — Atualiza arquivos fora da boundary impl (pyproject.toml, roadmap.schema.json)
para alinhar a 0.4.1.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)

    py = root / "pyproject.toml"
    if py.exists():
        txt = py.read_text(encoding="utf-8")
        txt2 = re.sub(r'(?m)^version\s*=\s*"0\.4\.0"', 'version = "0.4.1"', txt)
        if txt != txt2:
            py.write_text(txt2, encoding="utf-8")
            print("pyproject.toml -> 0.4.1")
        else:
            print("pyproject.toml ja em 0.4.1 ou nao encontrado padrao")

    rsj = root / ".roadmap/roadmap.schema.json"
    if rsj.exists():
        data = json.loads(rsj.read_text(encoding="utf-8"))
        sv = data.get("properties", {}).get("meta", {}).get("properties", {}).get("schema_version", {})
        if sv.get("const") == "0.4.0":
            sv["const"] = "0.4.1"
            rsj.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("roadmap.schema.json const -> 0.4.1")
        else:
            print(f"roadmap.schema.json const ja em {sv.get('const')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
