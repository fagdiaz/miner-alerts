# Quickstart: Hashcore Capability Inventory

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 021 confirms monitor/service liveness.
- Toolkit location is read from local config without displaying it or settings.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_hashcore_inventory tests.test_monitor_incidents tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile tools\hashcore_inventory.py app\miner_monitor.py
```

## Controlled Runtime Validation

1. Fingerprint the local Toolkit without printing sensitive paths.
2. Run only approved help/version discovery with no-window and timeout.
3. Review sanitization before adding artifacts to Git.
4. Compare candidates against existing diagnostics and close action scope unchanged.

## Evidence To Capture

- Toolkit version/fingerprint without sensitive path.
- Invocation allowlist, exit codes, timeouts and sanitized shapes.
- Complete risk matrix.
- Secret/address scan.
- Invariant showing reboot/restart action code/templates unchanged.
