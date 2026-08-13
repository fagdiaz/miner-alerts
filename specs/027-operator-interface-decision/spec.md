# Feature Specification: Operator Interface Decision

**Feature Branch**: `027-operator-interface-decision`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Evaluate Telegram, static HTML and Grafana against real operator workflows, and build a local-only FastAPI read-only MVP only if a measured workflow remains unsolved.

**Risk Class**: MEDIUM

**Dependencies**: Spec 025 Grafana evaluation and Spec 028 backup/restore proof

## User Scenarios & Testing

### User Story 1 - Choose the smallest sufficient interface (Priority: P1)

The operator evaluates common tasks across Telegram, static dashboard and Grafana using measurable time and completeness.

**Why this priority**: Another service is justified only by a real workflow gap.

**Independent Test**: Run the documented workflow scorecard with current interfaces.

**Acceptance Scenarios**:

1. **Given** all critical workflows meet targets, **When** the decision gate runs, **Then** no new API/UI is built
2. **Given** a critical read-only workflow remains unmet, **When** the gate runs, **Then** the exact gap and MVP scope are approved

---

### User Story 2 - Query incidents locally (Priority: P2)

If approved, a local API/UI filters miners, incidents and assessments without direct miner IO.

**Why this priority**: Historical investigation may need richer filtering than Telegram or fixed panels.

**Independent Test**: Query deterministic SQLite fixtures through read-only endpoints and optional server-rendered views.

**Acceptance Scenarios**:

1. **Given** an approved gap exists, **When** the local MVP runs, **Then** the operator can complete that workflow within target time
2. **Given** a query is invalid or the database unavailable, **When** the UI responds, **Then** a safe bounded error appears without changing monitor operation

---

### User Story 3 - Keep control in Telegram (Priority: P1)

The web surface exposes no reboot, restart, confirmation, config edit or miner proxy endpoint.

**Why this priority**: A second action surface would require authentication and a new high-risk security model.

**Independent Test**: Audit routes, OpenAPI and UI actions for mutation verbs and monitor imports.

**Acceptance Scenarios**:

1. **Given** the MVP is built, **When** routes and schema are audited, **Then** every endpoint is read-only
2. **Given** a user attempts a mutation method, **When** the server handles it, **Then** no action occurs and the method is rejected

### Edge Cases

- Grafana already solves every workflow.
- SQLite is locked, missing or migrating.
- The local server is accidentally bound beyond loopback.
- A query could return unbounded history.
- An incident contains sensitive raw evidence.

## Requirements

### Functional Requirements

- **FR-001**: The interface decision MUST score actual operator workflows before implementation.
- **FR-002**: If existing interfaces meet all P1 workflow targets, the spec MUST close with no new web service.
- **FR-003**: A conditional MVP MUST bind to loopback only and MUST expose read-only data.
- **FR-004**: The MVP MUST open SQLite in read-only mode and MUST NOT call miners, Telegram actions or Hashcore.
- **FR-005**: Allowed resources MUST be limited to health, miners, incidents, assessments and bounded history.
- **FR-006**: All list endpoints and views MUST have bounded pagination and time windows.
- **FR-007**: OpenAPI and validation MUST be generated from typed schemas if FastAPI is approved.
- **FR-008**: HTMX or server-rendered HTML MAY be used only for the approved workflow; React MUST NOT be added by default.
- **FR-009**: No config editor, action endpoint, credential display or remote network exposure is in scope.
- **FR-010**: Errors and stale data MUST be explicit and MUST NOT affect the monitor.
- **FR-011**: A future remote or action UI MUST require a separate security/action spec.

### Key Entities

- **WorkflowScore**: Measured operator task, interface, completion time and gap.
- **InterfaceDecision**: No-build or approved-MVP result with rationale.
- **ReadOnlyMinerView**: Current sanitized miner and freshness representation.
- **IncidentView**: Bounded incident, facts and assessment projection.
- **ApiHealth**: Database age, schema compatibility and service state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every P1 workflow has a measured result and explicit owner interface.
- **SC-002**: No MVP is created when current interfaces meet targets.
- **SC-003**: If built, all routes bind to loopback and pass a no-mutation/action-import audit.
- **SC-004**: Approved workflows complete within two minutes using the MVP.
- **SC-005**: Stopping the interface leaves monitoring, Telegram and actions unchanged.

## Assumptions

- One trusted local Windows operator is the initial user.
- Grafana and static HTML remain available read-only alternatives.
- Remote/mobile browser access is out of scope unless separately secured.

## Non-Goals

- Replacing Telegram as the remote action channel.
- Web reboot/restart/config controls.
- React SPA, public hosting, SSO or cloud deployment.
- Direct live miner queries from the UI.
