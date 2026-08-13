# Research: Monitor Liveness Watchdog

## Baseline Findings

- SCM can report running while application work is stalled.
- The global mutex blocks duplicate monitors but does not report a hung owner.
- The monitor already has process, tick, queue and worker timing points suitable for a sanitized heartbeat.
- Windows services and scheduled automation should remain non-interactive.

## Decisions

1. Combine SCM failure actions with an independent tick-heartbeat watchdog.
2. Use atomic JSON because this tiny cross-process contract does not justify a broker.
3. Keep notification dedupe in watchdog-local ignored state.
4. Treat backward clock movement as unknown/stale until tick sequence progresses.

## Rejected Or Deferred Alternatives

- A second monitor instance because it duplicates polling and action authority.
- WebSockets as a liveness fix because they do not supervise their owner process.
- OpenTelemetry Collector because it is disproportionate for this single-host heartbeat.

## External Validation Sources

- Microsoft SERVICE_FAILURE_ACTIONS: https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_failure_actionsw
- Microsoft service guidance: https://learn.microsoft.com/en-us/windows/win32/rstmgr/guidelines-for-services
- Microsoft interactive service warning: https://learn.microsoft.com/en-us/windows/win32/services/interactive-services
