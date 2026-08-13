# Feature Specification: V2 Release Stabilization

**Feature Branch**: `029-v2-release-stabilization`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Integrate and stabilize the accepted roadmap capabilities, execute cross-feature regression and disaster-recovery proof, reconcile documentation, and produce a production release candidate without adding features.

**Risk Class**: HIGH

**Dependencies**: Specs 021, 022, 023, 024, 025, 026, 027 and 028 accepted, blocked with evidence, or explicitly deferred; no open P0/P1 rollout regression

## User Scenarios & Testing

### User Story 1 - Prove end-to-end operational safety (Priority: P1)

The operator can trust alerts, commands, liveness, acquisition, evidence and action gates together after a controlled restart.

**Why this priority**: Individually passing features may still conflict at integration boundaries.

**Independent Test**: Run the full release matrix in QA and controlled production with exact evidence.

**Acceptance Scenarios**:

1. **Given** all accepted specs are integrated, **When** the release matrix runs, **Then** no state, polling-offset, Telegram or action invariant regresses
2. **Given** a P0 or P1 regression appears, **When** stabilization runs, **Then** release is blocked and the issue is isolated before more rollout

---

### User Story 2 - Prove recoverability (Priority: P1)

A verified backup restores to staging and operations can recover using current runbooks.

**Why this priority**: A stable release needs data recovery, not only runtime tests.

**Independent Test**: Execute the Spec 028 restore drill using release-candidate schema and compare required data.

**Acceptance Scenarios**:

1. **Given** the release database backup is selected, **When** restore drill runs, **Then** integrity, schema and key counts pass
2. **Given** restore validation fails, **When** release is evaluated, **Then** the candidate is blocked

---

### User Story 3 - Close one coherent documentation baseline (Priority: P1)

README, runbook, roadmap, calendar, strategies, active statuses and development log all describe the same deployed system.

**Why this priority**: Operational drift is a production risk.

**Independent Test**: Run link, terminology, date, status, secret and cross-artifact audits.

**Acceptance Scenarios**:

1. **Given** the release candidate is ready, **When** documentation sweep runs, **Then** every current capability and deferred item has one consistent status
2. **Given** runtime evidence is missing, **When** docs are reviewed, **Then** the item remains pending rather than complete

### Edge Cases

- One conditional spec closed as no-build or blocked.
- A dependency version changed during the program.
- A service restart requires elevation and cannot be observed.
- A P1 issue appears late in the soak.
- A backup restores but a newer optional table is absent.

## Requirements

### Functional Requirements

- **FR-001**: Stabilization MUST add no new feature or action capability.
- **FR-002**: Every accepted spec MUST have complete tasks, evidence, rollout and required observation status.
- **FR-003**: The full automated suite and Python/PowerShell/config syntax checks MUST pass from a clean environment.
- **FR-004**: State machine, auto-reboot gates, startup sanitization, cooldown/window, mutex and Telegram polling offset MUST receive explicit regression evidence.
- **FR-005**: All dangerous Telegram actions MUST retain confirmation and QA blocked-action proof.
- **FR-006**: Liveness, acquisition, episodes, incident assessment, metrics, backup and optional interface boundaries MUST be tested together.
- **FR-007**: A release-candidate SQLite backup and staging restore drill MUST pass.
- **FR-008**: Service activation MUST prove new PID, config source, mutex, QA mode, startup guard, database and worker health.
- **FR-009**: The candidate MUST complete a 72-hour observation period and a final seven-day reliability review with no unresolved P0/P1 issue.
- **FR-010**: Documentation MUST be synchronized and secrets/runtime artifacts MUST be absent from Git.
- **FR-011**: Deferred, blocked and no-build decisions MUST remain explicit and MUST NOT be represented as implemented.

### Key Entities

- **ReleaseCandidate**: Commit/dependency/config-example/schema identity under validation.
- **ValidationResult**: Command, environment, expected and observed result.
- **RegressionMatrix**: Cross-feature safety and operator workflow coverage.
- **ReleaseBlocker**: P0/P1 issue with owner, containment and retest evidence.
- **ReleaseEvidenceBundle**: Sanitized links to tests, runtime, restore and docs audit.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All required automated and runtime matrix checks pass with exact evidence.
- **SC-002**: No unresolved P0/P1 issue remains after 72 hours and the seven-day review.
- **SC-003**: A release-candidate backup restores successfully to staging.
- **SC-004**: No duplicate monitor, immediate persisted-state reboot, command silence or polling reprocessing is observed.
- **SC-005**: All canonical docs and spec statuses agree and Git contains no secret/runtime artifact.

## Assumptions

- Conditional specs may close blocked or no-build when their documented gate is satisfied.
- One controlled elevated maintenance window is available.
- Release tagging/commit occurs only after user approval outside this planning task.

## Non-Goals

- Adding features during stabilization.
- Expanding Hashcore or web action scope.
- Replacing Windows native monitor deployment.
- Claiming production readiness without the observation window.
