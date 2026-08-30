# Evidence: Hashcore Capability Inventory

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 021 liveness stability and local Hashcore Toolkit availability.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Static Installation Evidence - 2026-08-13

- Local config was read only to resolve the configured Toolkit files; no config
  value or absolute path was written to an artifact.
- `toolkit_cli.bat` exists, is 181 bytes and has SHA-256 prefix `2c204d87`.
- Static wrapper inspection shows a direct `%*` pass-through to
  `hashcore-toolkit.exe cli`; the wrapper is not an allowlist.
- `hashcore-toolkit.exe` exists, is 808,960 bytes and has SHA-256 prefix
  `9db18421`.
- Windows file metadata reports product/file version `1.6.0+167`.
- Production config has non-empty templates for exactly `reboot` and `restart`.
- No batch/executable process was started, no miner was contacted and no
  settings payload was read during this inspection.
- No vendor-proven invocation evidence is present, so
  `contracts/discovery-allowlist.md` is deliberately empty and invocation is
  blocked. This is planning evidence, not implementation completion.

## Required Evidence Before Completion

- Toolkit version/fingerprint without sensitive path.
- Full installation fingerprints in the future normalized artifact; the
  prefixes above are planning identifiers only.
- Zero-process tests for metadata-only, absent allowlist, fingerprint mismatch
  and invalid argv.
- Invocation allowlist, exit codes, timeouts and sanitized shapes.
- Complete risk matrix.
- Secret/address scan.
- Invariant showing reboot/restart action code/templates unchanged.

## Implementation And Verification Evidence (T001-T018) — 2026-08-29

- **T001 (Action Seam Hashes)**:
  * Current `app/miner_monitor.py` Hashcore action seam (lines 1654-1768, `_hashcore_cli_path`, `run_hashcore_discovery`, `run_hashcore_cli`): SHA-256 is `c31064ce2d5120ff26506acd91affb58b8ded64ff463cab0424f18ad70034039`.
  * Templates verified: `reboot_args_template: ['reboot', '{host}-{host}']`, `restart_args_template: ['restart', '{host}-{host}']`.
- **T002-T003 (Metadata-Only Baseline & Empty Allowlist)**:
  * Static installation inspection reproduced cleanly in metadata-only mode without subprocess creation or miner IO.
  * Vendor allowlist remains intentionally empty (`contracts/discovery-allowlist.md`), preserving the mandatory `blocked` process-discovery result.
- **T004-T006 (Comprehensive Test Suite)**:
  * Created `tests/test_hashcore_inventory.py` with 10 unit tests covering:
    - Zero subprocess execution in metadata-only mode.
    - Zero subprocess execution for absent, empty, or mismatched allowlists.
    - Strict rejection of argv containing templates, IP addresses, paths, or secrets.
    - Fingerprint invalidation upon hash mismatch.
    - Conservative command risk classification (`read_only`, `mutating`, `unknown`).
    - Subprocess execution constraints (`shell=False`, `stdin=DEVNULL`, `CREATE_NO_WINDOW`, 10s timeout, 64 KiB stream bounds).
    - Secret, path, and IP address sanitization.
  * All 10 tests PASS; full test suite grows to 381 tests PASS.
- **T007-T011 (Standalone Inventory Tool)**:
  * Implemented `tools/hashcore_inventory.py` with metadata-only default and zero monitor imports.
  * Generated deterministic sanitized artifact: `artifacts/spec026-hashcore-inventory.json`.
  * Verified installation fingerprints:
    - Wrapper (`toolkit_cli.bat`): 181 bytes, SHA-256 `2c204d87365dd94231b62c42cde5f5adbc219f1842cfae3c4bead35f4a338daf`.
    - Executable (`hashcore-toolkit.exe`): 808,960 bytes, SHA-256 `9db1842103c6abdea30913b9a3b0e0abcb3ba2fd103b689c45caee98312847eb`.
    - Windows PE Product Version: `1.6.0+167`.
    - Shape: `argv_passthrough`.
- **T012-T014 (Capability Assessment)**:
  * Since process discovery is blocked pending vendor documentation, zero integration candidates are accepted (`candidates: []`).
- **T015-T018 (Validation & Closeout)**:
  * `py_compile` on `tools/hashcore_inventory.py` and `tests/test_hashcore_inventory.py`: OK.
  * Production monitor call sites and action scope remain 100% unchanged.

## Runtime Rollout

- Metadata-only inventory tool implemented, tested, and executed in production environment.
- Process discovery remains blocked pending vendor allowlist approval.
- Production monitor is completely uncoupled and unaffected.
