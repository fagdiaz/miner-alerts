# Evidence: QA Poll-Empty Stability

## Status

Implementation, local validation and controlled runtime activation complete.

## Baseline Defect

- In parent commit `8af2a6a`, `POLL_EMPTY` is followed by a QA-only interpolation of `action` and `cmd_start`.
- Both names are command-local and may be unbound when the first poll is empty.
- The outer polling exception handler catches the resulting error and enters backoff.

## Test-First Evidence

The focused source regression test failed before the patch:

```text
AssertionError: 'action' unexpectedly found in
"log(f'POLL_EMPTY ...')\nif qa_mode:\n log_pid(... action ... cmd_start ...)"
```

After removing only that misplaced QA log, the same test passed.

## Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_telegram_polling_stability -v
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
git diff -- app/miner_monitor.py
git diff --check
Get-Service MinerAlerts
```

Results:

- Focused regression: 1/1 PASS after the expected red phase.
- Full suite: 81/81 PASS.
- Python compilation and diff check: PASS.
- Speckit QA preflight with builds: PASS, requirements checklist 10/10.
- Application diff: exactly two deleted lines under `POLL_EMPTY`; the offset,
  dispatch, backoff, sleep, monitoring, and action paths are unchanged.
- Windows service: `MinerAlerts` remains `Running`, start type `Automatic`.

## Runtime Boundary

No second polling worker was started and the production service was not restarted.
The new code will be activated in the final controlled rollout.
