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

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
