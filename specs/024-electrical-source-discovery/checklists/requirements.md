# Specification Quality Checklist: Electrical Source Discovery

**Purpose**: Validate specification completeness before implementation
**Created**: 2026-08-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Focuses on operator value and production risk.
- [x] Mandatory sections are complete.
- [x] Scope and non-goals are explicit.
- [x] No real secrets, addresses, tokens or runtime data are included.

## Requirement Completeness

- [x] No unresolved clarification markers remain.
- [x] Requirements are testable and unambiguous.
- [x] Success criteria are measurable.
- [x] Acceptance scenarios and edge cases are defined.
- [x] Dependencies and assumptions are identified.

## Safety Readiness

- [x] Action authority and read-only boundaries are explicit.
- [x] Negative paths and stale/missing evidence are covered.
- [x] Validation extends beyond `py_compile`.
- [x] Runtime rollout and observation evidence are required before completion.
- [x] Current chain/PSU evidence is explicitly distinguished from direct AC measurement.
- [x] Supported/unsupported/blocked capability report fields are exact.
- [x] Protocol operation allowlists prohibit generic scans and every write path.
- [x] Collector cadence, one-in-flight and no-carry-forward behavior are bounded.
- [x] Missing hardware remains a valid blocked closeout.
