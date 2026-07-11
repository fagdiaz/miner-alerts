# Implementation Plan: Read-Only Miner Diagnostics

## Approach

Create a standalone stdlib-only tool under `tools/` so the running monitor and
Windows service are not touched.

## Design

- `tools/miner_diagnostics.py`
  - Reads config.
  - Supports `--dry-run`.
  - Queries ASIC API 4028 via sockets.
  - Extracts normalized fields.
  - Writes sanitized markdown and JSON evidence.
- `Dockerfile.diagnostics`
  - Runs the collector with mounted config and output directory.
- `.dockerignore`
  - Excludes secrets, logs, caches, and runtime state.

## Validation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run
```

## Rollback

Remove the added diagnostics tool, Dockerfile, docs, and spec files. No runtime
state or monitor behavior is affected.
