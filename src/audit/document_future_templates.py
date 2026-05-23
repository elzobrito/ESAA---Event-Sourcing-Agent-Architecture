#!/usr/bin/env python3
"""FIX-1531 — Cria docs/spec/activity_future_templates.md documentando o arquivo."""
from __future__ import annotations
import argparse
from pathlib import Path

DOC = """# activity_future_templates.jsonl

## Status: experimental / nao consumido pelo runtime

O arquivo `.roadmap/activity_future_templates.jsonl` contem **templates** de
eventos hipoteticos previstos para evolucao futura do protocolo ESAA. Ele:

- **nao e lido** por `esaa.store.parse_event_store`;
- **nao afeta** projecoes (`roadmap.json`/`issues.json`/`lessons.json`);
- **nao afeta** `esaa verify` ou `esaa replay`;
- serve como **referencia de design** para acoes/eventos ainda nao implementados.

## Quando usar

Ao propor uma nova acao no vocabulario, adicione um template no arquivo (sem
event_seq, sem ts) ilustrando a estrutura esperada. Quando implementada, o
template e movido para o event store canonico com event_seq real, e a entrada
removida deste arquivo.

## Garantia de nao-contaminacao

O runtime so consome `.roadmap/activity.jsonl` (ver `EVENT_STORE_PATH` em
`src/esaa/constants.py`). Qualquer outro arquivo `.jsonl` em `.roadmap/` e
ignorado.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    target = Path(args.root) / "docs/spec/activity_future_templates.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DOC, encoding="utf-8")
    print(f"wrote: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
