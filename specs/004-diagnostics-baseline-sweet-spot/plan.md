# Implementation Plan: Diagnostics Baseline Sweet Spot

## Approach

Add a standalone stdlib-only analyzer under `tools/` that consumes diagnostic
snapshots and produces an operator-readable baseline.

## Design

- `tools/diagnostics_baseline.py`
  - Accepts `--input` as file or directory.
  - Finds `snapshot.json` files.
  - Aggregates per-miner metrics.
  - Writes markdown and JSON outputs.
- No changes to the running monitor.

## Validation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\diagnostics_baseline.py
& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline
```
