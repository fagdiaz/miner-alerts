# Research: Adaptive Acquisition Resilience

## Baseline Findings

- API 4028 calls are bounded socket requests in the monitor process.
- Count-based hysteresis means faster authoritative sampling would change behavior.
- ThreadPoolExecutor is sufficient for four IO-bound endpoints.
- Vnish WebSockets already serve a separate firmware-evidence role.

## Decisions

1. Preserve one authoritative sample per 30-second epoch.
2. Use limited concurrency to remove cross-miner head-of-line blocking.
3. Separate diagnostic evidence at the data-contract level.
4. Never exponentially back off authoritative outage checks.

## Rejected Or Deferred Alternatives

- Health WebSockets because API 4028 does not publish them.
- Unbounded threads because they create request storms.
- Faster authoritative polling because it changes hysteresis semantics.
- An asyncio rewrite because it is disproportionate at current scale.

## External Validation Sources

- WebSocket protocol: https://www.rfc-editor.org/rfc/rfc6455
- Python concurrent futures: https://docs.python.org/3/library/concurrent.futures.html
