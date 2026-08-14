# Contract: Electrical Measurements And Collector

## Measurement

```text
source_id / channel
metric: ac_voltage_v | ac_current_a | active_power_w | line_frequency_hz | energy_wh
value: finite number
unit: V | A | W | Hz | Wh
observed_ts / ingested_ts
clock_quality: source_verified | source_offset | host_ingest | unknown
quality: valid | stale | invalid | timeout | error | unsupported
reason_code
capability_version / measurement_map_version
```

No raw payload, endpoint or credential is persisted.

## Stable Reasons

- `ok`;
- `source_timeout`;
- `transport_error`;
- `payload_invalid`;
- `measurement_missing`;
- `unit_mismatch`;
- `value_non_finite`;
- `value_out_of_documented_range`;
- `source_clock_unknown`;
- `source_stale`;
- `operation_not_allowlisted`.

Unknown qualities/reasons fail closed and cannot become current evidence.

## Collection Run

Each run records source, scheduled/start/completion time, request count,
measurement count, status and stable reason. It stores no raw body or exception
message. Exactly one in-flight request per source is allowed; no same-interval
retry is allowed.

## Freshness

Freshness is derived from the capability report's documented update cadence and
the configured collection interval. An old value is never carried forward as a
new sample. On source failure, collector health records missing evidence and
the previous sample ages naturally.

## Failure And Safety Contract

- No SNMP SET, Modbus write, HTTP mutation or MQTT publish operation exists.
- No generic scan/walk exists.
- No chain/hashboard field is normalized as an AC measurement.
- No secret appears in output, persistence, diagnostics or logs.
- No action decision consumes electrical evidence.
- Adapter/collector failure cannot affect API 4028 monitoring.

## Compatibility

- Core monitor operates when source is disabled, absent or blocked.
- Tables are additive and optional.
- Spec 023 treats electrical evidence as advisory and source-referenced.
