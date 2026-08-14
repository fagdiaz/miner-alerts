# Data Model: Adaptive Acquisition Resilience

## AcquisitionEpoch

- `epoch_id`: Monotonic identity.
- `scheduled_ts / deadline_ts`: Timing boundary.
- `completed_ts`: Fleet completion.
- `expected_count / completed_count`: Completeness.
- `status`: current, completed, expired or skipped; expired/skipped epochs never
  dispatch or mutate state.

## MinerSampleEnvelope

- `miner_key`: Stable identity.
- `authority`: authoritative or diagnostic.
- `observed_ts / completed_monotonic / latency_ms`: Freshness and bounded
  completion evidence.
- `responded / rate_ths / elapsed_seconds / active_boards`: Normalized signal.
- `quality`: valid, partial, invalid, timeout, error or late.
- `reason_code`: Stable explanation.
- `epoch_id`: Authoritative epoch reference.
- `summary_entry / stats_response`: Ephemeral compatibility payloads consumed
  by existing normalizers; never exported as metric labels or persisted whole.
- `summary_requests / stats_requests`: Integer budget evidence for this sample.

## PollHealth

- `consecutive_timeouts`: Bounded counter.
- `last_success_ts`: Latest valid authoritative success.
- `latency_window`: Bounded values with a fixed maximum length.
- `in_flight`: Overlap state.
- `last_epoch_duration_ms / last_epoch_completed_count`: Fleet completion.
- `last_epoch_quality_counts`: Bounded counts by stable quality.
- `last_epoch_summary_requests / last_epoch_stats_requests`: Budget evidence.
- `skipped_epoch_count`: Monotonic process-local count, never replay work.
- `fleet_reason_code`: `none` or a stable aggregate transport classification.

## InFlightLease

- `miner_key / authority`: Owner identity and request class.
- `epoch_id / acquired_monotonic / deadline_monotonic`: Bounded lifetime.
- `request_count`: Summary/stats budget consumed by the lease.

## Invariants

- Only authoritative envelopes cross the state/action boundary.
- Exactly one authoritative envelope exists per miner and epoch.
- Late results cannot be reassigned.
- Prior values retain their original timestamp.
- A resumed scheduler never materializes missed epoch IDs as requests.
- Disabled adaptive mode preserves the sequential envelope order and action
  boundary.
- Envelope collection order is `valid_miners` order, never future completion
  order.
- State/action calculations continue to use one tick-level evaluation time;
  observation timestamps add evidence but do not accelerate timers.
- Raw API payloads and exception text are not persisted as PollHealth.
