# Feature Specification: Incident Evidence Fusion

**Feature Branch**: `023-incident-evidence-fusion`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Correlate episode, Vnish, mining-quality, pool, fleet and action evidence into conservative root-cause assessments that distinguish observed, suspected and confirmed facts.

**Risk Class**: MEDIUM

**Dependencies**: Spec 022 rollout and acquisition-quality evidence

## User Scenarios & Testing

### User Story 1 - One coherent assessment (Priority: P1)

An incident shows one chronological evidence summary instead of requiring manual comparison of commands and logs.

**Why this priority**: Fragmented evidence slows response and encourages unsupported cause claims.

**Independent Test**: Replay a known restart and LOW episode from persisted fixtures.

**Acceptance Scenarios**:

1. **Given** an incident has state, firmware and quality facts, **When** assessment is requested, **Then** one bounded timeline identifies source and time
2. **Given** sources disagree, **When** assessment is rendered, **Then** the conflict is visible and no cause becomes confirmed
3. **Given** the same persisted rows, explicit window and ruleset are replayed, **When** assessment runs twice, **Then** semantic output and evidence digest are identical

---

### User Story 2 - Conservative confidence (Priority: P1)

Every conclusion is labeled observed, suspected or confirmed with support, contradictions and missing evidence.

**Why this priority**: Reducing unnecessary reboots requires honest uncertainty.

**Independent Test**: Evaluate isolated, fleet, thermal, board and unknown fixtures.

**Acceptance Scenarios**:

1. **Given** only temporal proximity exists, **When** a cause is scored, **Then** it is at most suspected
2. **Given** direct source evidence and matching symptoms exist, **When** a cause is scored, **Then** it may be confirmed under the versioned rule
3. **Given** a source is stale, partial, late or clock-uncertain, **When** it is evaluated, **Then** it remains visible but cannot promote an ordering-sensitive cause

---

### User Story 3 - Fleet pattern visibility (Priority: P2)

Simultaneous miner symptoms are grouped without automatically claiming an electrical fault.

**Why this priority**: Shared timing changes diagnosis but does not prove voltage fluctuation.

**Independent Test**: Compare synchronized and independent incident fixtures.

**Acceptance Scenarios**:

1. **Given** several miners degrade inside the fleet window, **When** assessment runs, **Then** a fleet-pattern observation appears
2. **Given** power data is absent, **When** fleet pattern appears, **Then** electrical cause remains unconfirmed
3. **Given** fusion is disabled or unavailable, **When** diagnosis is requested, **Then** the existing read-only diagnosis remains available without changing actions

### Edge Cases

- Vnish source clock is unparsed.
- A source or collector is stale.
- An incident predates one data table.
- One fact could match adjacent episodes.
- Manual and automatic actions occur near one restart.
- A newer valid fact contradicts an older irregular fact.
- The collector completes partially or returns no relevant events.
- A source timestamp is in the future beyond clock-skew tolerance.
- Assessment persistence fails after a valid read-only result is calculated.

## Requirements

### Functional Requirements

- **FR-001**: Assessments MUST use persisted timestamped evidence and bounded current context only.
- **FR-002**: Every fact MUST identify source, observed time, freshness, clock quality and normalized code.
- **FR-003**: Conclusions MUST be separated into observed, suspected and confirmed.
- **FR-004**: Temporal proximity alone MUST NOT confirm causality.
- **FR-005**: Supporting, contradicting and missing evidence MUST remain visible.
- **FR-006**: Fleet correlation MUST use a bounded window and MUST NOT assert electrical cause without external power evidence.
- **FR-007**: Action attribution MUST reuse recorded action outcomes and the existing attribution window.
- **FR-008**: Assessment generation MUST be read-only with respect to miners, state and actions.
- **FR-009**: Persisted assessments MUST preserve ruleset version and source references for replay.
- **FR-010**: Stale or clock-uncertain evidence MUST lower confidence deterministically.
- **FR-011**: Telegram and dashboard detail MUST share one assessment renderer.
- **FR-012**: Assessment rules MUST receive an explicit assessment time, use stable ordering and produce a canonical evidence digest independent of creation time or database-generated IDs.
- **FR-013**: Fusion MUST be disabled by default and MUST preserve the existing diagnosis path when disabled, unavailable or over budget.
- **FR-014**: Source reads MUST be indexed, bounded by miner/time/limit and avoid per-row query growth.
- **FR-015**: Unknown fact or cause codes MUST fail closed and MUST NOT promote confidence.

### Key Entities

- **EvidenceFact**: Immutable normalized observation with source, time and confidence ceiling.
- **IncidentAssessment**: Versioned findings, hypotheses, contradictions and missing evidence.
- **CauseHypothesis**: Candidate cause linked to supporting and contradicting facts.
- **MinerBaseline**: Stable operating bands derived from eligible historical samples.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Known fixtures produce deterministic assessments across repeated runs.
- **SC-002**: No timing-only fixture yields a confirmed cause.
- **SC-003**: Every conclusion links to persisted facts and exposes contradiction or missing evidence.
- **SC-004**: Fleet patterns are recognized without changing action decisions.
- **SC-005**: A 24-hour bounded assessment completes under two seconds at current scale.
- **SC-006**: Enabling or disabling fusion changes no state transition, persisted streak, reboot decision or Hashcore invocation in deterministic regression tests.
- **SC-007**: Migration and repeated-save tests preserve old readers and store at most one assessment for the same subject, ruleset and evidence digest.

## Assumptions

- Existing SQLite data supports initial replay with one additive assessment migration.
- Current stability, quality, restart and Vnish analyzers are reused.
- Electrical evidence remains optional until Spec 024 proves a source.
- Spec 022 persists or exposes authoritative acquisition quality and stable reason codes before Spec 023 implementation begins.

## Non-Goals

- Automatic remediation or reboot choice.
- Opaque machine learning or LLM diagnosis.
- Replacing raw event and diagnosis commands.
