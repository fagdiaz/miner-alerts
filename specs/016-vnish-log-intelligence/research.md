# Research: Vnish Log Intelligence

## Deployed Interface Evidence

- The deployed first miner reports Vnish `fw_version=1.2.7`, model `s19jpro`.
- HTTP GET returned 200 for `/api/v1/summary`, `/api/v1/chains`, and `/api/v1/metrics`.
- The deployed SPA creates WebSockets at `/api/v1/logs-ws/<tab>` for `status`, `miner`, `autotune`, and `system`.
- A bounded read-only connection to `status` returned historical lines for initialization, cooling, autotune, mining start/stop, pool configuration failure, and `Restarting ... Chain break detected`.

## Primary Documentation

- Vnish documents diagnostic report export and log access in its firmware UI: https://www.vnish.net/FAQ/index.html
- Vnish documents common log evidence and distinguishes normal autotune/calibration from chain, thermal, power, pool, and watchdog failures: https://vnish-firmware.com/faq/bitmain-antminer-logs-errors/
- Vnish release notes describe `/summary`, `/chains`, `/factory-info`, `/metrics` evolution and log behavior: https://vnish-firmware.com/firmware/

## Decision: RFC 6455 Library

Use `websocket-client` only in the collector CLI. It is a mature synchronous client that handles fragmented frames, ping/pong, close frames, and socket timeouts more safely than a local protocol implementation. The core monitor does not import it.

## Decision: Normalized Events Only

The database stores generated summaries and SHA-256 fingerprints. Raw messages remain transient because logs may contain pool/user details and can be large.

## Decision: Advisory V1

Events feed diagnosis, Telegram history, and dashboard timelines only. They do not alter state or actions until production collection establishes precision and timing.

## Alternatives Considered

- Poll undocumented HTTP log routes: rejected; deployed routes returned 404 and the SPA proves WebSocket usage.
- Add persistent WebSocket threads to the monitor: rejected for v1 to isolate protocol failures from monitoring/actions.
- Store complete logs: rejected for privacy, size, and diagnostic-noise reasons.
