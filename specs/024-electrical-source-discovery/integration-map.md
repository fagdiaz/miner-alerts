# Integration Map: Electrical Source Discovery

## Current Evidence Boundary

The repository currently has no proven external AC measurement source, no PDU,
UPS or meter adapter, no electrical collector task and no electrical sample
table. Existing voltage/power-like fields are miner-domain evidence:

| Current field/code | Unit/domain | Valid interpretation | Prohibited interpretation |
| --- | --- | --- | --- |
| `chain_voltage_mv_avg` | mV, hashboard/chain | Average internal chain voltage reported by firmware | AC mains/input voltage |
| `chain_power_w_total` | W, hashboard chains | Firmware-reported/derived chain consumption | Calibrated wall/PDU active power |
| `frequency_mhz_avg` | MHz, ASIC tuning | Average chip/chain frequency | AC line frequency |
| `max_temp_c` | C, miner sensors | Maximum reported miner temperature | Ambient/PSU/mains measurement unless source says so |
| `chain_voltage_abnormal` | firmware event | Firmware reported an internal chain-voltage condition | Measured AC fluctuation |
| `psu_error` / `power_voltage_low/high` | firmware event | PSU/firmware reported a condition | Direct volts/amps/watts or confirmed external cause |

These facts remain useful incident evidence, but their confidence ceiling for an
external electrical cause is `suspected` under Spec 023.

## Discovery State At Planning Time

- ASIC API 4028/Vnish: available, but not a direct AC source.
- Network-managed PDU/UPS/meter: no physical identity or endpoint is configured
  in tracked code/docs.
- PSU management interface: no model-specific read-only telemetry contract is
  proven.
- Manual electrical reading: may be attached as operator evidence later, but is
  not a continuous collector source.

Therefore Spec 024 is discovery-ready but adapter-blocked until the operator
identifies actual hardware and documented read access. This is a valid planned
outcome, not a reason to infer AC values.

## Discovery Workflow

1. Record a sanitized physical inventory: device class, vendor, model, firmware
   and which miners/outlets/phases it covers.
2. Obtain vendor documentation for measurement keys/registers/OIDs/endpoints,
   units, scaling, update cadence, source clock and authentication.
3. Classify the source `supported`, `unsupported` or `blocked` before installing
   any protocol dependency.
4. Build a read-operation allowlist from exact vendor documentation.
5. Capture one sanitized fixture without credentials, addresses, serials or
   site-specific names.
6. Add red normalization/no-write/load tests.
7. Only then implement one source-specific adapter in shadow mode.

Discovery never performs generic network, SNMP OID or Modbus register scans.

## Protocol No-Write Boundary

| Protocol | Allowed after documentation | Prohibited |
| --- | --- | --- |
| SNMPv3 | GET, GETNEXT or GETBULK on exact allowlisted measurement OIDs | SET, trap configuration, discovery walk outside allowlist |
| Modbus TCP | Function 0x03/0x04 on exact documented ranges | 0x05, 0x06, 0x0F, 0x10, 0x16, 0x17 and generic register scanning |
| Vendor HTTPS | GET/HEAD on exact read-only telemetry endpoint | POST, PUT, PATCH, DELETE, session/config/action endpoints |
| MQTT | Subscribe to exact existing telemetry topics from a real publisher | Publish, retained-command topics, provisioning a broker as a fake source |

Static tests inspect adapters and fixtures for prohibited methods/function
codes. Runtime request construction also rejects any operation outside the
source-specific allowlist.

## Normalized Measurement Keys

The first adapter may emit only documented values from this finite vocabulary:

- `ac_voltage_v`;
- `ac_current_a`;
- `active_power_w`;
- `line_frequency_hz`;
- `energy_wh`.

Every measurement includes `source_id`, `channel`, value, SI unit, source time
when available, ingestion time, clock quality, quality and reason code. Phase
or outlet identity is a bounded channel defined by the capability report.

No anomaly is inferred without a documented nominal/range for that exact source
and measurement. A valid sample with no range remains valid evidence with no
anomaly classification.

## Collection Budget

- One collector process and at most one in-flight request per physical source.
- No faster than the documented source update cadence and never faster than one
  request per five seconds.
- One bounded timeout shorter than the collection interval.
- No retry inside the same interval; failure becomes an explicit sample/run
  reason.
- Modbus contiguous documented registers are grouped into the minimum read
  requests supported by the device.
- Collection has its own health record and cannot block the 30-second miner tick.

## Planned Persistence

| Table | Purpose | Safety boundary |
| --- | --- | --- |
| `electrical_sources` | Sanitized source capability/version/status | No endpoint or credential |
| `electrical_samples` | Timestamped normalized values/quality | Additive; no miner state/action field |
| `electrical_collector_runs` | Attempts, success/failure, duration and reason | No raw response or secret |

EventStore queries are bounded by source/channel/metric/time with indexes. Spec
023 receives persisted fact references and remains read-only.

## Correlation Boundary

- A fresh documented out-of-range value is an observed electrical anomaly.
- Temporal proximity to an incident may produce a suspected relation.
- Miner simultaneity without external measurements is missing electrical
  evidence, not an anomaly.
- Stale, missing, clock-uncertain or unit-mismatched values cannot confirm order.
- Electrical evidence never enters state transitions, sustained LOW,
  auto-reboot, manual action confirmation or Hashcore.

## Activation And Rollback

1. Close discovery as blocked if no source is proven.
2. If supported, implement/test one adapter with collection disabled.
3. Run 72-hour read-only shadow collection and compare source clock, gaps,
   request load and incident windows.
4. Enable only advisory Spec 023 rendering after review.
5. Roll back by disabling/removing the collector; miner monitoring and source
   evidence remain unchanged.
