# Minimal ESAA Project

## Windows PowerShell

```powershell
python -m pip install esaa-core==0.5.0b1
mkdir esaa-minimal
cd esaa-minimal
esaa bootstrap --profile public
esaa init
esaa verify
esaa eligible
```

## Linux/macOS

```bash
python -m pip install esaa-core==0.5.0b1
mkdir esaa-minimal
cd esaa-minimal
esaa bootstrap --profile public
esaa init
esaa verify
esaa eligible
```

## Notes

Use `esaa submit`, `esaa claim`, `esaa complete`, and `esaa review` to move
tasks through the governed ESAA state machine. The event store remains
append-only and read models are generated from replay.
