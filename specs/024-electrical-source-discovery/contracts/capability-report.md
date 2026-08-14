# Contract: Electrical Source Capability Report

## Required Identity

- `report_version` and creation time;
- `source_id`: sanitized logical identifier;
- device class: PDU, UPS, meter or documented PSU interface;
- vendor/model/firmware references without serial number or address;
- coverage: bounded logical channels/phases/outlets;
- result: `supported`, `unsupported` or `blocked`.

## Required Protocol Evidence

- selected protocol and authentication mode;
- exact read operation allowlist;
- exact measurement OID/register/endpoint/topic map;
- raw unit, scale/transform and normalized SI unit;
- documented update cadence and source-clock behavior;
- timeout/request budget;
- vendor documentation reference and version/date;
- sanitized fixture reference.

Credentials, endpoint addresses, community strings, usernames, certificates,
serials and site names are never included.

## Result Rules

### Supported

Requires all identity/protocol/measurement fields, a sanitized sample, explicit
units/scaling, read-only allowlist and static no-write proof.

### Unsupported

Used when the identified device/documentation proves no usable read-only
electrical measurement exists.

### Blocked

Used when device identity, documentation, access, authentication approval or a
safe fixture is missing. Blocked is the mandatory result when evidence is
insufficient.

## Measurement Map Entry

```text
normalized_key
channel_kind
protocol_location
read_operation
raw_type
raw_unit
scale / offset
normalized_unit
valid_range (only if documented)
source_timestamp_field (optional)
```

No generic register/OID/key guessing is allowed.

## Approval Gate

Adapter/dependency/schema work may start only after a supported report is
reviewed and linked from `evidence.md`. Any report change that alters protocol,
map, unit or scaling resets adapter fixtures and the 72-hour shadow gate.
