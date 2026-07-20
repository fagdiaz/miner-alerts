# Research: Vnish Evidence And Technology Selection

## Evidence Available In This Repository

The sanitized diagnostic snapshot for all four current miners exposes chain data
under `STATS[1]`, not necessarily `STATS[0]`. Observed useful fields include:

- `chain_vol1..3`: approximately 12,440 to 13,225.
- `chain_consumption1..3`: approximately 832 to 902.
- `freq_avg1..3`: approximately 482 to 519.
- `chain_hw1..3`: mostly zero, with one observed value of 22.
- `fan1..4`, `fan_pwm`, chip and PCB temperature fields.
- Pool rejected/stale counters in the standalone diagnostics snapshot.

The production monitor currently asks for `stats` each tick but reads only one
entry for active boards. This feature will inspect all entries for observational
telemetry while preserving the existing state-machine input.

## Decisions

### Keep SQLite And Add An Additive Migration

**Decision**: Use schema v2 with `PRAGMA user_version`, additive telemetry columns,
and a dedicated `reboot_decisions` table.

**Rationale**: Current volume is small, writes are serialized, WAL is already in
use, and no external service or credential is required. SQLite also supports a
future read-only API without changing the collector.

### Normalize Instead Of Storing Raw ASIC Responses

**Decision**: Persist scalar aggregates and short diagnostic flags only.

**Rationale**: Raw responses are firmware-specific, large, can contain pool
identifiers, and make migrations/querying harder. Sanitized raw captures remain a
manual diagnostics artifact outside Git.

### Treat Voltage Conservatively

**Decision**: Name the metric `chain_voltage_mv_avg` and label it as firmware
chain/board voltage, never AC input voltage.

**Rationale**: Values and field names support millivolt-scale chain voltage, but
they do not prove wall input quality. AC fluctuation requires PSU/PDU/UPS evidence.

### Do Not Add Runtime Pool/Version Calls Yet

**Decision**: The production loop will reuse its existing `stats` call only.

**Rationale**: Sequential `pools` and `version` calls could extend every sampling
cycle under network failure. The standalone collector already captures those
fields safely. A bounded background enrichment design remains separate work.

### Defer Web Frameworks And Containers

**Decision**: No FastAPI, dashboard, Prometheus, Grafana, Docker, or additional
process in Spec 007.

**Rationale**: They are viable contemporary tools for a later read-only interface,
but they do not fix ambiguous reboot decisions. A stable evidence schema and
queries are prerequisite. The existing service also depends on Windows-hosted
Hashcore Toolkit paths that should not be moved into a container casually.

## Alternatives Rejected For This Increment

- **JSONL decision log**: weak indexed correlation and retention compared with the existing database.
- **InfluxDB/TimescaleDB**: disproportionate operational dependency at current fleet size.
- **Raw Vnish log ingestion**: source/path and taxonomy are not yet proven on deployed firmware.
- **Policy scoring/model**: unsafe before a representative historical dataset exists.
