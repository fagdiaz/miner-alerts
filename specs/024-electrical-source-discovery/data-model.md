# Data Model: Electrical Source Discovery

## ElectricalSource

- `source_id`: Stable physical identity.
- `vendor / model / firmware`: Capability context.
- `protocol / endpoint`: Selected read-only transport.
- `measurement_map_version`: Documented field/register map.
- `auth_mode`: Secret-free authentication description.
- `status`: Supported, unsupported or blocked.
- `read_allowlist / update_interval / timeout`: Proven bounded operations.
- `capability_version / measurement_map_version`: Fixture compatibility.

## ElectricalMeasurement

- `source_id / channel`: Origin and phase/outlet.
- `metric`: voltage, current, power, frequency or energy.
- `value / unit`: Normalized SI value.
- `observed_ts / ingested_ts`: Time evidence.
- `quality`: Valid, stale, invalid, timeout, error or unsupported.
- `reason_code`: Stable finite normalization/transport reason.

## ElectricalCollectorRun

- `source_id / scheduled_ts / started_ts / completed_ts`.
- `request_count / measurement_count / duration_seconds`.
- `status / reason_code`: Sanitized bounded result.
- No raw body, endpoint, credential or exception message.

## PowerIncidentCorrelation

- `incident_id`: Assessment subject.
- `measurement_ids`: Direct facts.
- `window_seconds`: Bounded relation.
- `classification`: Observed anomaly, suspected relation or missing evidence.

## Invariants

- No write-capable operation is callable.
- Units are explicit and never inferred from field names alone.
- Stale values are not current.
- Collector failure never carries a previous value forward.
- Generic scans and non-allowlisted operations are invalid.
- Power data cannot authorize a miner action.
