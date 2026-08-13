# Research: Hashcore Capability Inventory

## Baseline Findings

- Current config exposes only reboot and restart argument templates.
- Hashcore runs through a Windows batch/CLI path and can create consoles unless no-window flags are used.
- Toolkit command surface and installed version are not committed.
- Read-only capability value depends on overlap with API 4028 and Vnish evidence.

## Decisions

1. Inventory the installed version before designing integrations.
2. Run only help/version invocations proven non-mutating.
3. Treat every ambiguous operation as prohibited.
4. Require one new spec per accepted capability integration.

## Rejected Or Deferred Alternatives

- Trying likely command names against production miners.
- Expanding reboot/restart scope during inventory.
- Storing raw settings or output that may contain secrets.
- Building a generic wrapper before output contracts are known.

## External Validation Sources

- Local Toolkit help/version output is the primary source; vendor documentation must be recorded when available.
- Windows non-interactive service guidance: https://learn.microsoft.com/en-us/windows/win32/services/interactive-services
