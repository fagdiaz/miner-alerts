# Research: Hashcore Capability Inventory

## Baseline Findings

- Current config exposes only reboot and restart argument templates.
- Hashcore runs through a Windows batch/CLI path and can create consoles unless no-window flags are used.
- Toolkit command surface and installed version are not committed.
- Read-only capability value depends on overlap with API 4028 and Vnish evidence.
- Static inspection found a 181-byte `toolkit_cli.bat` wrapper that forwards
  arbitrary `%*` arguments to `hashcore-toolkit.exe cli`; it enforces no
  command policy.
- Static PE metadata identifies the local executable as Hashcore Toolkit
  `1.6.0+167`. Wrapper/executable SHA-256 prefixes were captured only to bind the
  planning baseline; full fingerprints belong in the future sanitized artifact.
- Neither wrapper nor executable was started during this planning inspection.

## Decisions

1. Make metadata-only fingerprinting the default and separate it from process
   discovery.
2. Treat the installed wrapper as a transport adapter, never as an allowlist.
3. Require vendor evidence and exact fingerprints before approving any fixed
   help/version argv; the current allowlist is empty.
4. Run an approved argv at most once, sequentially, with no-window,
   `shell=False`, disabled stdin, 10-second timeout and bounded streams.
5. Treat every ambiguous operation as prohibited.
6. Require one new spec per accepted capability integration.

## Rejected Or Deferred Alternatives

- Trying likely command names against production miners.
- Expanding reboot/restart scope during inventory.
- Storing raw settings or output that may contain secrets.
- Building a generic wrapper before output contracts are known.
- Treating existing selftest/discovery calls as proof that the same invocations
  are safe for a new inventory tool.
- Passing miner/settings arguments to discover command syntax.
- Capturing unbounded raw process output or committing local paths.

## External Validation Sources

- Static file/PE metadata is authoritative for installation identity only.
- Vendor documentation or a trusted versioned sample is required before local
  help/version output may be collected by Spec 026.
- Windows non-interactive service guidance: https://learn.microsoft.com/en-us/windows/win32/services/interactive-services
