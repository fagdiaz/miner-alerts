# Data Model: Adaptive Acquisition Resilience

## AcquisitionEpoch

- `epoch_id`: Monotonic identity.
- `scheduled_ts / deadline_ts`: Timing boundary.
- `completed_ts`: Fleet completion.
- `expected_count / completed_count`: Completeness.

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

## Invariants

- Only authoritative envelopes cross the state/action boundary.
- Exactly one authoritative envelope exists per miner and epoch.
- Late results cannot be reassigned.
- Prior values retain their original timestamp.
