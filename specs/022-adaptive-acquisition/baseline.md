# Sequential Acquisition Baseline

**Captured**: 2026-08-13 22:05-22:12 ART

**Status**: Preliminary pre-D+1 baseline. It does not complete T001 because
direct per-request/tick-duration percentiles still require approved
instrumentation after the implementation gate.

## Static Request Boundary

Source inspection of the production loop establishes:

1. One tick-level `now_ts` is captured.
2. Miners are evaluated in configured order.
3. `read_summary(host, port)` makes one `summary` request with default timeout
   5 seconds.
4. Only a responsive summary calls `read_stats_snapshot(host, port)`, making one
   `stats` request with default timeout 5 seconds.
5. State, persistence, episodes and action policy execute inline before the next
   miner.
6. One heartbeat is written after all miners, followed by
   `time.sleep(poll_seconds)`; production `poll_seconds` is 30.

Therefore the static per-tick budget is one summary per miner plus one
conditional stats per responsive miner, with no retry in these wrappers. For the
current four-miner fleet this is 4-8 requests per completed tick. Manual Telegram
reads are separate and unchanged.

## Passive Heartbeat Timing Sample

The heartbeat file was read locally every 200 ms until seven consecutive tick
sequences were observed. No miner, Telegram, Hashcore, service or config call was
made by the sampler.

| Metric | Result |
| --- | --- |
| Consecutive sequences | 546 through 552 |
| Intervals | 6 |
| Minimum | 30.191 s |
| Median | 30.216 s |
| Mean | 30.224 s |
| P95 nearest-rank for this small sample | 30.247 s |
| Maximum | 30.275 s |

Raw interval values were `30.206`, `30.204`, `30.225`, `30.191`, `30.247` and
`30.275` seconds. This measures completed-heartbeat cadence, not individual
request latency. The approximately 0.2-second residual above the configured
30-second sleep is not treated as direct tick-duration evidence because scheduler
and file-observation jitter are included.

## Concurrent Runtime Context

- Windows service remained `Running` and `Automatic`.
- Monitor heartbeat PID remained `35788`, queue depth was zero and Telegram
  poller/sender ages remained under the configured liveness threshold.
- Watchdog log contained 283 consecutive samples from process start at the
  preceding D0 check, with cadence coverage 1.0, zero unhealthy samples and zero
  watchdog actions.
- Latest persisted sample showed all four miners `OK`, finite rates from 91.24
  through 101.37 TH/s and no automatic action since process start.
- Latest Vnish collector run recovered from the earlier partial result to `ok`
  with 16/16 streams.

## Remaining Baseline Evidence

After Spec 021 D+1 passes, T001 still needs controlled instrumentation for:

- summary and stats latency distributions separately;
- full tick processing duration excluding the 30-second sleep;
- per-miner request counts observed rather than statically inferred;
- timeout/partial behavior under deterministic fixtures.

No source, example config, local config or production runtime was changed to
obtain this baseline.
