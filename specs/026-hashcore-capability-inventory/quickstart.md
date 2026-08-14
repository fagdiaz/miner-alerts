# Quickstart: Hashcore Capability Inventory

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 021 confirms monitor/service liveness.
- Toolkit location is read from local config without displaying it or settings.
- Metadata-only is the default. Invocation remains blocked while
  `contracts/discovery-allowlist.md` has no approved entry.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_hashcore_inventory tests.test_monitor_incidents tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile tools\hashcore_inventory.py app\miner_monitor.py
```

## Metadata-Only Inventory

Once implemented, the default command performs static reads only:

```powershell
& ".\.venv\Scripts\python.exe" tools\hashcore_inventory.py `
  --config app\config.json `
  --metadata-only
```

Expected result today: installation metadata plus `blocked` process-discovery
status. No wrapper/executable process, miner IO or settings read is permitted.

Process discovery must not be attempted until the allowlist contract contains a
reviewed exact-fingerprint entry. The tool must require both an explicit
`--invoke-approved` flag and the reviewed allowlist path; either one missing is
a zero-process rejection.

## Controlled Runtime Validation

1. Fingerprint the local Toolkit without printing sensitive paths or starting a process.
2. Verify missing/mismatched allowlist paths start zero subprocesses.
3. Only after vendor review, run fixed approved discovery with no-window,
   disabled stdin, bounded streams and timeout.
4. Review sanitization before adding artifacts to Git.
5. Compare candidates against existing diagnostics and close action scope unchanged.

## Evidence To Capture

- Toolkit version/fingerprint without sensitive path.
- Zero-subprocess proof for metadata-only and all blocked conditions.
- Invocation allowlist, exit codes, timeouts and sanitized shapes.
- Complete risk matrix.
- Secret/address scan.
- Invariant showing reboot/restart action code/templates unchanged.
