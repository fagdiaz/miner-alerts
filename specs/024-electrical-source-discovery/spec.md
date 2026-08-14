# Feature Specification: Electrical Source Discovery

**Feature Branch**: `024-electrical-source-discovery`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Determine whether trustworthy AC input voltage, current and power telemetry exists, select one read-only protocol only after hardware discovery, and correlate it with incidents without authorizing reboots.

**Risk Class**: MEDIUM

**Dependencies**: Spec 023 evidence contract plus access to the actual PDU, UPS, meter or PSU documentation

## User Scenarios & Testing

### User Story 1 - Know whether AC evidence exists (Priority: P1)

The operator receives an explicit supported or blocked result for each possible electrical source.

**Why this priority**: Chain voltage from miners is not AC input and must not be mislabeled.

**Independent Test**: Complete a hardware/protocol inventory with documentation and sanitized sample evidence.

**Acceptance Scenarios**:

1. **Given** no suitable device exposes telemetry, **When** discovery closes, **Then** the result is blocked with the missing hardware dependency
2. **Given** a device exposes read-only measurements, **When** discovery closes, **Then** units, protocol, authentication and source clock are documented

---

### User Story 2 - Collect trustworthy power samples (Priority: P1)

When a source is proven, bounded read-only samples capture volts, amps and watts with quality and timestamps.

**Why this priority**: Power correlations are useful only when units and freshness are reliable.

**Independent Test**: Replay valid, stale, out-of-range, timeout and unit-mismatch adapter fixtures.

**Acceptance Scenarios**:

1. **Given** a valid device sample arrives, **When** it is normalized, **Then** source, units, time and quality are persisted
2. **Given** a read fails, **When** collection completes, **Then** missing evidence is explicit and no old value becomes current

---

### User Story 3 - Correlate without overclaiming (Priority: P2)

Incident detail can show nearby power anomalies while keeping cause advisory.

**Why this priority**: Simultaneous fleet symptoms do not prove an electrical event.

**Independent Test**: Compare incidents with direct anomaly, stale data and no source.

**Acceptance Scenarios**:

1. **Given** voltage is outside a documented device range near an incident, **When** assessment runs, **Then** an observed power anomaly is shown
2. **Given** only miners fail together, **When** assessment runs, **Then** power cause remains missing or suspected, never confirmed

### Edge Cases

- The device exposes only cumulative energy, not instantaneous voltage.
- Three-phase measurements have per-phase units.
- Device time differs from host time.
- SNMP/Modbus registers differ by firmware.
- The selected source becomes unavailable during an incident.

## Requirements

### Functional Requirements

- **FR-001**: Discovery MUST identify physical model, firmware, protocol, measurement points, units, update rate and authentication before adapter work.
- **FR-002**: Miner chain or hashboard voltage MUST NOT be labeled as AC input voltage.
- **FR-003**: If no reliable source exists, the spec MUST close as blocked rather than infer power from miner behavior.
- **FR-004**: The selected adapter MUST be read-only and MUST NOT issue SNMP SET, Modbus write or vendor mutation requests.
- **FR-005**: Protocol preference MUST follow actual support: SNMPv3, Modbus TCP, vendor HTTPS, then MQTT from a real publisher.
- **FR-006**: Every sample MUST carry source, measurement key, value, unit, observed time, ingestion time and quality.
- **FR-007**: Out-of-range, stale, missing and clock-uncertain samples MUST be explicit.
- **FR-008**: Power evidence MAY enrich incident assessment but MUST NOT authorize restart or reboot.
- **FR-009**: Credentials MUST stay in local config or OS secret storage and never enter diagnostics or Git.
- **FR-010**: Collection load and device request limits MUST be bounded and documented.
- **FR-011**: Discovery and collection MUST enforce a source-specific read-operation allowlist and MUST NOT perform generic network, OID or register scans.
- **FR-012**: Collector failures MUST be persisted separately from values and MUST NOT carry a previous measurement forward as current.

### Key Entities

- **ElectricalSource**: Physical device and proven read-only protocol capability.
- **ElectricalMeasurement**: Normalized volts, amps, watts, frequency or energy sample.
- **SourceCapabilityReport**: Supported, unsupported or blocked discovery evidence.
- **PowerIncidentCorrelation**: Bounded advisory relation between measurements and an incident.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every candidate source has a supported, unsupported or blocked conclusion with evidence.
- **SC-002**: No documentation or UI labels chain voltage as AC input.
- **SC-003**: All adapter fixtures preserve units, source time and quality.
- **SC-004**: No electrical path contains a write operation or action authorization.
- **SC-005**: A power-source outage remains visible and cannot silently reuse stale measurements.
- **SC-006**: Static/runtime fixtures reject every prohibited protocol operation and prove one in-flight request per source at no faster than documented cadence or five seconds.

## Assumptions

- Hardware identity may require operator access to labels or vendor UI.
- Network management remains on the trusted local network.
- A source-specific adapter is conditional on discovery success.

## Non-Goals

- Installing new metering hardware automatically.
- Controlling breakers, PDU outlets or PSU settings.
- Auto-rebooting from voltage anomalies.
