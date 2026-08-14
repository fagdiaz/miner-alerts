# Integration Map: Adaptive Acquisition Resilience

**Status**: Pre-implementation map; no runtime integration exists yet.

## Current Authoritative Path

The production authority is the single `while True` loop in
`app/miner_monitor.py::main`.

1. A tick captures one `now_ts` and iterates `valid_miners` in configuration
   order.
2. `read_summary()` issues one API 4028 `summary` request with a five-second
   socket timeout.
3. Only when summary responds, `read_stats_snapshot()` issues one `stats`
   request with the same timeout.
4. Vnish and mining-quality normalization consume the raw summary/stats
   dictionaries.
5. QA state forcing, streak updates, state transitions, telemetry persistence,
   restart attribution, auto-reboot policy, episode notifications and status
   rendering execute inline for that miner.
6. After every miner, the tick publishes the status snapshot, persists state,
   writes one heartbeat and sleeps for `poll_seconds`.

Consequences that must remain explicit:

- Current cadence is full sequential tick duration plus `poll_seconds`; it is
  not an exact wall-clock 30-second scheduler.
- Completion order and evaluation order are currently identical to
  `valid_miners` order.
- One tick-level `now_ts` drives all streak, episode and action calculations,
  even though network observations complete at different real times.
- Stats is conditional on a successful summary. Normal budget is therefore
  one or two requests per responsive miner and one request per failed miner.

## Existing Transport Limitation

`_read_command()` intentionally preserves a simple compatibility contract:
payload dictionary on success and `None` on connection, timeout, empty payload
or JSON failure. It logs the exception but discards the structured cause.

Spec 022 needs explicit timeout/error/invalid reasons without changing manual
command behavior. The implementation seam is therefore:

1. Add a typed low-level transport outcome used by scheduled acquisition.
2. Keep `_read_command()`, `read_summary()`, `read_stats_snapshot()` and all
   existing manual callers compatible through wrappers.
3. Do not infer timeout versus parse error from elapsed time or log text.
4. Store only stable reason codes in envelopes; exception messages, addresses
   and raw payloads are not metrics labels or persisted diagnostics.

Stable minimum reason vocabulary:

| Quality | Reason code | Meaning |
| --- | --- | --- |
| `valid` | `ok` | Summary is usable; stats is usable or not required. |
| `partial` | `stats_missing` | Summary is usable but stats has no usable board data. |
| `invalid` | `empty_payload` | Transport completed without a payload. |
| `invalid` | `invalid_json` | Payload cannot be decoded as the expected JSON object. |
| `invalid` | `summary_missing` | Response exists but has no usable summary record. |
| `invalid` | `rate_invalid` | Summary exists but rate is absent or non-finite. |
| `timeout` | `transport_timeout` | Connect or receive exceeded its bounded timeout. |
| `error` | `transport_error` | Refused, reset or other bounded socket failure. |
| `late` | `epoch_deadline_exceeded` | Result completed after its authoritative epoch deadline. |
| `error` | `scheduled_overlap` | A prior scheduled lease still owns this miner. |

## Planned Scheduler Boundary

The scheduler runs once near the current tick start, before any per-miner state
mutation. It returns an ordered mapping keyed by the existing `state_key`.
Completion order is never exposed to the state machine.

```text
valid_miners
  -> acquisition epoch (bounded IO only)
  -> one ordered authoritative envelope per configured miner
  -> existing per-miner evaluation in valid_miners order
  -> existing state/action/episode/persistence path
```

The existing evaluation path receives the same logical values:

- `rate_ths`
- `elapsed`
- `responded`
- `summary_entry`
- `active_boards`
- `stats_response`

`observed_ts`, latency, quality and reason remain additional evidence. The
current tick-level `now_ts` remains the state/action clock so bounded
concurrency cannot accelerate sustained LOW, hysteresis, cooldown or episode
semantics.

## Ordering, Deadlines And Leases

- Epoch IDs are monotonic in-process and are never reconstructed from wall
  clock time.
- A delayed or resumed scheduler creates one current epoch. It does not create
  request work for missed IDs.
- Two workers is the safe default for the current four-miner fleet.
- Each scheduled miner owns at most one lease across authoritative and optional
  diagnostic requests.
- A socket call already running at deadline is not force-killed. Its result is
  classified late and ignored by state/action processing.
- A lease remains owned until the worker exits, preventing a late socket from
  overlapping the next scheduled request.
- Authoritative outage checks do not back off or retry. The next eligible
  current epoch may try once after the lease is free.

## Manual Telegram IO Boundary

Current `/info` and `/selftest` handlers perform independent live reads. Spec
022 does not move them into the scheduler, count them against fleet budgets or
alter their cooldown/reply behavior.

The per-miner lease contract applies to scheduler-owned authoritative and
diagnostic requests. Existing manual command IO may overlap scheduled IO; any
manual result remains read-only and cannot become an authoritative envelope.
This preserves current command behavior while making scheduler request counts
deterministic.

## Integration Anchors

| Anchor | Required treatment |
| --- | --- |
| `main`: config near `poll_seconds` | Read disabled-safe acquisition options; no implicit enablement. |
| `main`: tick start before `for miner in valid_miners` | Build exactly one fleet epoch or call sequential fallback. |
| Current summary/stats calls inside miner loop | Replace only with ordered envelope unpacking after parity tests pass. |
| QA force-state block | Keep after envelope unpacking, unchanged. |
| Streak/state transition block | Keep ordered and unchanged. |
| Restart/auto-reboot/episode blocks | Accept authoritative values only; no diagnostic input. |
| State save and heartbeat | Preserve once per completed tick. Add bounded PollHealth only as evidence. |
| Telegram poller and offset | No scheduler dependency and no behavior change. |

## Deterministic Contract Matrix

| Scenario | Envelope/result | State/action expectation |
| --- | --- | --- |
| Four fast miners | Four ordered valid envelopes | Sequential parity. |
| One summary timeout | One timeout plus three timely peer envelopes | No peer head-of-line delay beyond SC-001. |
| Summary valid, stats absent | Partial envelope with usable summary | Preserve current non-HASHBOARD behavior when boards are unknown. |
| Invalid/non-finite rate | Invalid envelope | Never classify healthy or actionable from that value. |
| Result after deadline | Late envelope for its original epoch | Never reassigned or applied. |
| Lease still active next epoch | Scheduled-overlap envelope, no new socket | Exactly one envelope and no overlap. |
| Host resumes after multiple periods | One current epoch | Zero catch-up requests/streaks. |
| All endpoints transport-fail | Individual failures plus fleet health reason | Preserve per-miner authoritative evidence. |
| Diagnostic sees recovery | Diagnostic envelope | Read-only context only; no streak/timer/action mutation. |
| `/info` overlaps epoch | Independent command response | No epoch-budget or authority mutation. |
| Feature flag disabled | Sequential fallback envelopes | Ordered state/action parity with baseline. |

## Activation And Rollback

1. Before Spec 021 D+1: documentation, source mapping and test design only.
2. After Spec 021 D+1: red contracts and isolated acquisition implementation.
3. Before Spec 021 D+3: no production activation.
4. After D+3: disabled-path parity, QA, 24-hour shadow and rollback rehearsal
   still precede controlled enablement.
5. Rollback is `adaptive_acquisition_enabled=false`; it must not require a
   schema rollback, service reinstall or state-file conversion.
