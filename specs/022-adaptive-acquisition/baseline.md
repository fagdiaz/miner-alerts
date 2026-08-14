# Sequential Acquisition Baseline

**Captured**: 2026-08-13 22:05-22:12 ART

**Status**: T001 complete with static, passive-heartbeat and controlled
read-only API 4028 evidence.

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

## Controlled Sequential API 4028 Sample - 2026-08-14

`tools/acquisition_baseline.py` reproduced the current configured-order path in
a separate process: one five-second `summary`, then one five-second `stats` only
when the summary responded, with zero retries. It wrote only generic
`miner-1`...`miner-4` labels to an ignored atomic JSON artifact.

Ten samples against four miners produced:

| Metric | Result |
| --- | --- |
| Summary requests | 40/40 successful |
| Conditional stats requests | 40/40 successful |
| Automatic retries | 0 |
| Sequential cycle minimum | 140.734 ms |
| Sequential cycle P50 | 171.031 ms |
| Sequential cycle mean | 172.670 ms |
| Sequential cycle P95 / maximum | 204.077 ms |
| Effective interval estimate P50 | 30.171 s |
| Effective interval estimate P95 | 30.204 s |

Across generic miners, summary P50 ranged from 19.878 to 24.909 ms and summary
P95 from 30.939 to 44.513 ms. Stats P50 ranged from 13.412 to 16.487 ms and
stats P95 from 31.606 to 43.081 ms.

The first sandboxed invocation was excluded because local-network access was
denied and all outcomes were typed `error`. The authoritative run was repeated
with explicit local-network permission and atomically replaced that artifact.
After capture, the service retained the same PID, fresh tick/workers, queue zero
and healthy watchdog. No state, action, Telegram or Hashcore path was invoked.

## Remaining Baseline Evidence

Shadow comparison still needs the same metrics from the disabled/integrated
adaptive path before activation. That belongs to T012, not T001.

No monitor source, example/local config or production runtime was changed to
obtain this baseline; only the standalone read-only tool and its tests were
added.
