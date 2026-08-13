# Data Model: Electrical Source Discovery

## ElectricalSource

- `source_id`: Stable physical identity.
- `vendor / model / firmware`: Capability context.
- `protocol / endpoint`: Selected read-only transport.
- `measurement_map_version`: Documented field/register map.
- `auth_mode`: Secret-free authentication description.
- `status`: Supported, unsupported or blocked.

## ElectricalMeasurement

- `source_id / channel`: Origin and phase/outlet.
- `metric`: voltage, current, power, frequency or energy.
- `value / unit`: Normalized SI value.
- `observed_ts / ingested_ts`: Time evidence.
- `quality / reason_code`: Valid, stale, invalid, timeout or unsupported.

## PowerIncidentCorrelation

- `incident_id`: Assessment subject.
- `measurement_ids`: Direct facts.
- `window_seconds`: Bounded relation.
- `classification`: Observed anomaly, suspected relation or missing evidence.

## Invariants

- No write-capable operation is callable.
- Units are explicit and never inferred from field names alone.
- Stale values are not current.
- Power data cannot authorize a miner action.
