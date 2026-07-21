# Evidence: Vnish Transition Reboot Interlock

## Status

Implementation, local validation and controlled production activation complete.

## Baseline

- Mining Quality already extracts current transition markers from existing `STATS` data.
- The current auto-reboot interlock supports thermal and fleet evidence but does not consume transition evidence.
- Live read-only samples collected for Spec 013 showed zero transitioning chains; synthetic tests are required for the active-transition path.

## Test-First Evidence

Before implementation, the focused tests failed on:

- missing `INTERLOCK_FIRMWARE_TRANSITION` and transition parameters;
- missing `/why` rendering for the new decision reason.

After implementation, the focused policy, persistence, and rendering suite passed.

## Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_reboot_safety tests.test_reboot_decision_audit tests.test_event_store -v
& ".\.venv\Scripts\python.exe" -m py_compile app\reboot_safety.py app\event_store.py app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
& ".\.venv\Scripts\python.exe" -c "import json,pathlib; c=json.loads(pathlib.Path('app/config.example.json').read_text(encoding='utf-8')); assert c['auto_reboot_firmware_transition_guard_enabled'] is True"
git diff --check
Get-Service MinerAlerts
```

Results:

- 25 focused policy/persistence tests: PASS.
- Full suite: 84/84 PASS.
- Python compilation, JSON default, and diff check: PASS.
- Speckit QA preflight with builds: PASS, requirements checklist 11/11.
- Synthetic policy probe: `allowed=False reason=firmware_transition transitioning_chains=1`.
- Source-order test proves the gate precedes cooldown/Hashcore and the transition
  guard is absent from `telegram_polling_worker`, preserving manual actions.
- No additional `read_summary`, `read_stats_snapshot`, or other miner IO was added.
- Windows service remains `Running`, start type `Automatic`.

## Runtime Boundary

The live read-only snapshots available today contained zero transitioning chains,
so a real Vnish transition block is not claimed as runtime-verified. The deterministic
synthetic gate and wiring are validated; final activation is deferred to rollout.
