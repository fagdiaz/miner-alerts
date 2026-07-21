# Evidence: Vnish Hashboard Detection

**Status**: Complete
**Service activation**: Completed by the controlled Spec 017 rollout.

## Current Payload Evidence

`diagnostics/latest/snapshot.json` reports for miners 23-26:

- `active_boards=3`
- positive `stats.STATS[1].chain_acn1`, `chain_acn2`, `chain_acn3`

## Validation Results

### Current sanitized miners

The production `_count_active_boards` parser was run against the candidate fields
captured in `diagnostics/latest/snapshot.json`:

```text
S19JPRO-23: boards=3
S19JPRO-24: boards=3
S19JPRO-25: boards=3
S19JPRO-26: boards=3
current-vnish-board-fixtures: PASS
```

### Syntax and tests

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m unittest discover -s tests -v
```

Result: PASS, 40 tests. New tests cover current `chain_acnN`, zero/malformed
values, unknown evidence, legacy list/scalar formats, multi-entry selection, and
source-level HASHBOARD-before-LOW/action precedence.

### QA and repository

- `git diff --check`: PASS; only expected CRLF conversion warnings.
- Speckit preflight: PASS, checklist 5/5.
- `Get-Service -Name MinerAlerts`: `Running`; no restart attempted.

## Safety Review

- No extra network I/O.
- Existing state transition order remains HASHBOARD before LOW.
- Auto-reboot still evaluates only LOW.
- No manual command, Hashcore call, QA guard, timer, polling, or storage behavior changed.
- Runtime activation remains unverified until the end-of-day controlled restart.
