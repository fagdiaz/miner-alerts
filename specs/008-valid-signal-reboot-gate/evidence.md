# Evidence: Valid Signal Auto-Reboot Gate

**Status**: Implementation and local validation complete  
**Service activation**: Deferred to the end-of-day controlled restart.

## Validation

### Syntax

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py app\\event_store.py app\\vnish_telemetry.py tools\\incident_report.py
```

Result: PASS, exit code 0.

### Tests

```powershell
& ".\\.venv\\Scripts\\python.exe" -m unittest discover -s tests -v
```

Result: PASS, 34 tests. New coverage proves:

- only a finite current rate below threshold is eligible;
- no response, `None`, NaN, and positive/negative infinity are invalid;
- a rate equal to or above threshold is `not_low`;
- invalid/recovered signal cannot pass the policy predicate;
- invalid/recovered signal clears `low_since_ts`, while eligible signal preserves it;
- runtime wiring keeps the independent uptime-reset cleanup and places Hashcore after the new gate.

### Repository And QA

- `git diff --check`: PASS; Git emitted only expected CRLF conversion warnings.
- Speckit HIGH-risk preflight with builds: PASS.
- Requirements checklist: 7/7 complete.
- Full previous storage, Telegram, restart intelligence, QA, and report tests remain green.

## Safety Comparison

- State transition conditions at `OFFLINE`, `HASHBOARD`, `LOW`, and `OK` are unchanged.
- No new `continue` was added to the outer signal gate.
- Existing eligible ordering remains startup guard -> sustained LOW -> cooldown -> window -> QA -> Hashcore.
- Manual reboot/restart/confirm, Telegram polling, offset, and notifications are untouched.
- The gate is stricter only for automatic action eligibility.

## Runtime

`Get-Service -Name MinerAlerts` remained `Running`. No service restart or second
monitor process was attempted. Live QA remains deferred to the end-of-day release.
