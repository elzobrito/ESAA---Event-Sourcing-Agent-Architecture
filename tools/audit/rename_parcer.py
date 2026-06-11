#!/usr/bin/env python3
"""FIX-1521 â€” Rename PARCER_PROFILE_agent-docs.yaml para PARCER_PROFILE.agent-docs.yaml.

Adota convencao '.' (4 dos 5 profiles ja usam). Atualiza referencias textuais
em CLAUDE.md e AGENTS.md. O evento 7 do event store permanece imutavel com o
nome antigo (registro historico valido).

Uso: python src/audit/rename_parcer.py --root <repo_root>
"""

from __future__ import annotations
import argparse, re, shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    old = root / ".roadmap/PARCER_PROFILE_agent-docs.yaml"
    new = root / ".roadmap/PARCER_PROFILE.agent-docs.yaml"
    if old.exists() and not new.exists():
        shutil.move(str(old), str(new))
        print(f"renamed: {old.name} -> {new.name}")
    elif new.exists():
        print("already renamed")
    else:
        print("source file not found; skipping")

    for ref in (root / ".claude/CLAUDE.md", root / "AGENTS.md"):
        if not ref.exists():
            continue
        txt = ref.read_text(encoding="utf-8")
        new_txt = re.sub(r"PARCER_PROFILE_agent-docs\.yaml", "PARCER_PROFILE.agent-docs.yaml", txt)
        if new_txt != txt:
            ref.write_text(new_txt, encoding="utf-8")
            print(f"updated refs in {ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
