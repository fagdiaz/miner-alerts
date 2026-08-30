# Evidence: Electrical Source Discovery

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 023 evidence contract plus access to the actual PDU, UPS, meter or PSU documentation.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Audited current source fields: chain voltage/power, ASIC frequency,
  temperature and firmware PSU codes are miner-domain observations, not direct
  AC measurements.
- Confirmed no tracked external PDU/UPS/meter source or adapter exists; adapter
  work remains blocked pending real hardware identity/documentation/access.
- Defined supported/unsupported/blocked capability reports, exact protocol
  read allowlists and prohibition of generic network/OID/register scanning.
- Defined finite SI measurement keys, source clocks, collector health,
  no-carry-forward, one-in-flight/no-retry load limits and advisory-only Spec
  023 correlation.
- This hardening changed documentation only. It did not probe the network,
  install a dependency, change config/schema/service or access a miner.

## Required Evidence Before Completion

- Capability matrix and vendor documentation reference.
- Sanitized sample and unit map.
- Read-only operation scan.
- Allowlist, no-scan, one-in-flight and cadence proof.
- Collector load, timeout and freshness report.
- Explicit supported or blocked decision.

## Discovery Gate Evidence (Phase 1: T001-T004) — 2026-08-29

- **T001 (Miner-Domain vs AC Inventory)**:
  * Audited all four Antminer S19j Pro units:
    - `chain_voltage_mv_avg` in `telemetry_samples`: measures DC voltage across hashboards (~13,000 to 14,500 mV) produced by internal buck converters; proven NOT to represent AC input line voltage.
    - `chain_power_w_total` in `telemetry_samples`: measures aggregate DC board power consumption (~3,000 W); proven NOT to represent AC line active power.
    - Vnish PSU alarms (`psu_error`, `power_voltage_low`, `power_voltage_high`): condition alerts without calibrated voltage/current telemetry.
- **T002 (Sanitized Capability Report)**:
  * Generated sanitized capability report artifact: `artifacts/spec024-electrical-capability-report.json`.
  * Preserved strict privacy: zero internal IP addresses, community strings, credentials or serial numbers included.
- **T003 (Hardware Dependency Status)**:
  * Physical/network inventory confirmed: no network-managed PDU (SNMP/Modbus/HTTP), no smart UPS, and no network energy meter is present on the mining subnet (`192.168.100.x`).
  * Missing hardware dependency formally recorded.
- **T004 (Gate Decision)**:
  * Formal Decision: **`blocked` (missing_hardware_dependency)**.
  * In accordance with `contracts/capability-report.md`, adapter development, third-party libraries and schema migrations are withheld.
  * No speculation or false inference of AC line voltage is permitted from hashboard DC signals.

## Runtime Rollout

- Blocked pending physical deployment of network-connected AC metering hardware.
- Do not mark this spec complete from checked tasks or compilation alone.
