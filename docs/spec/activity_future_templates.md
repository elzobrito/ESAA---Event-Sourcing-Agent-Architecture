# activity_future_templates.jsonl

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
