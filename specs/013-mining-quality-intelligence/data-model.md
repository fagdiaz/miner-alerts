# Data Model: Mining Quality Intelligence

## MiningQualityTelemetry

- `accepted_shares_total`: optional non-negative integer
- `rejected_shares_total`: optional non-negative integer
- `stale_shares_total`: optional non-negative integer
- `chain_fault_count`: optional non-negative integer
- `chains_not_mining_count`: optional non-negative integer
- `quality_flags`: bounded stable codes

## Telemetry Sample Schema v3

Additive columns on `telemetry_samples`:

- `accepted_shares_total INTEGER`
- `rejected_shares_total INTEGER`
- `stale_shares_total INTEGER`
- `chain_fault_count INTEGER`
- `chains_not_mining_count INTEGER`
- `quality_flags_json TEXT NOT NULL DEFAULT '[]'`

Existing rows keep null counters and an empty flag list.

## QualityDelta

- elapsed interval seconds
- accepted/rejected/stale deltas
- hardware-error delta
- derived rejected and stale percentages
- reset-detected flag

## QualityAssessment

- status: `learning`, `stable`, `watch`, or `critical`
- comparable sample count and confidence
- latest sample and calculated delta
- bounded reasons with stable code, severity, and text
