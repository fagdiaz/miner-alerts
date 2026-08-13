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
- `observed_ts / latency_ms`: Freshness.
- `responded / rate_ths / boards`: Normalized signal.
- `quality`: valid, partial, invalid, timeout, error or late.
- `reason_code`: Stable explanation.
- `epoch_id`: Authoritative epoch reference.

## PollHealth

- `consecutive_timeouts`: Bounded counter.
- `last_success_ts`: Latest valid authoritative success.
- `latency_window`: Bounded values.
- `in_flight`: Overlap state.

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
