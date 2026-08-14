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

## Runtime Rollout

- Not started.
- Static metadata inspection is complete; standalone tooling and invocation are
  not implemented.
- Do not mark this spec complete from checked tasks or compilation alone.
