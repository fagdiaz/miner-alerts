# Quickstart: Adaptive Acquisition Resilience

**Status**: Implemented and active in production (PID 38816, 2 workers). Gate D+1 passed (49+ hours continuous uptime, 5,900+ ticks). Gate D+3 soak completes 2026-08-30 16:11:40.

## Preconditions (All Passed)

- Spec 021 D+1 and D+3 closed with 77h soak and SCM recovery verified.
- Spec 020 episode/status behavior production-verified.
- Sequential acquisition baseline captured (`artifacts/spec022-sequential-baseline.json`).
- Pre-rollout invariants (T011) and shadow/rollback rehearsal (T012) verified with 371 tests PASS.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_acquisition tests.test_reboot_safety tests.test_telegram_polling_stability
& ".\.venv\Scripts\python.exe" -m unittest tests.test_acquisition_baseline
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\acquisition.py app\miner_monitor.py tools\acquisition_baseline.py
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
```

The controlled baseline command is read-only and writes a sanitized ignored
artifact:

```powershell
& ".\.venv\Scripts\python.exe" tools\acquisition_baseline.py --samples 10 --pause-seconds 1 --timeout-seconds 5 --output artifacts\spec022-sequential-baseline.json
```

Before activation, compare the example values with `contracts/config.md`.
Absence of the keys and explicit `adaptive_acquisition_enabled=false` must both
select the sequential path.

## Controlled Runtime Validation

1. Capture the sequential baseline: summary/stats request counts, full-tick
   duration, effective interval and sample age.
2. Run deterministic QA fixtures for fast, slow, timeout, partial-stats and
   transport-failure miners.
3. Verify late results and missed epochs are discarded, including host resume
   after suspend; no catch-up burst is allowed.
4. Verify per-miner and fleet request budgets, and prove diagnostic envelopes
   cannot mutate state or actions.
5. Run manual `/info` and `/selftest` during acquisition and prove their live IO
   remains outside authoritative epoch accounting.
6. Keep `adaptive_acquisition_enabled=false` and compare sequential output,
   state transitions and action decisions with the pre-change baseline.
7. Run 24 hours of production shadow metrics before enabling bounded
   acquisition.
8. Rehearse rollback to sequential acquisition, then observe activation at
   D+1/D+3 for request volume, age, alert timing and actions.

## Evidence To Capture

- Before/after request, latency and tick report.
- Envelope fixtures for partial, invalid, timeout, late, skipped and diagnostic
  handling.
- Numeric per-epoch/per-miner request-budget proof.
- Disabled-path parity and rollback rehearsal.
- State, action and Telegram-offset invariants.
- QA and D+1/D+3 runtime logs.
