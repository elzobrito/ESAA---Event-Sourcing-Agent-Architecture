#!/usr/bin/env python3
"""FIX-1541 — Amenda CLAUDE.md substituindo 'enforcement.mode=reject' por '{reject, require_field, require_step}'.

LES-0003 tem enforcement.mode=require_field, entao a redacao original (`mode=reject`)
e estreita demais. Esta amenda reflete o conjunto real de modos enforcaveis.
"""
from __future__ import annotations
import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    target = Path(args.root) / ".claude/CLAUDE.md"
    if not target.exists():
        print("CLAUDE.md not found; skipping")
        return 0
    txt = target.read_text(encoding="utf-8")
    old = "Trate cada lesson com `enforcement.mode=reject` como **constraint inviolável**"
    new = "Trate cada lesson com `enforcement.mode` em {`reject`, `require_field`, `require_step`} como **constraint inviolável**"
    if old in txt:
        txt = txt.replace(old, new)
        target.write_text(txt, encoding="utf-8")
        print("amended")
    elif new in txt:
        print("already amended")
    else:
        print("trecho nao encontrado; revise manualmente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
