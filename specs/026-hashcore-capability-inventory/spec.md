# Feature Specification: Hashcore Capability Inventory

**Feature Branch**: `026-hashcore-capability-inventory`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Inventory the installed Hashcore Toolkit version and command surface, classify every capability as read-only, mutating or unknown, and preserve the existing reboot/restart action boundary.

**Risk Class**: MEDIUM

**Dependencies**: Spec 021 liveness stability and local Hashcore Toolkit availability

## User Scenarios & Testing

### User Story 1 - Know the installed capability surface (Priority: P1)

The operator and developer have a versioned sanitized list of Toolkit commands, help and exit behavior.

**Why this priority**: Features cannot be safely planned from assumed vendor capabilities.

**Independent Test**: Run only approved discovery/help/version invocations against fixtures and the local installation.

**Acceptance Scenarios**:

1. **Given** Toolkit is installed, **When** inventory runs, **Then** version, path identity and discovered help are recorded without secrets
2. **Given** Toolkit is missing or help unsupported, **When** inventory runs, **Then** the result is explicit and no command is guessed

---

### User Story 2 - Classify command risk (Priority: P1)

Every discovered operation is marked read-only, mutating or unknown with evidence.

**Why this priority**: Unknown CLI behavior must not become a production action accidentally.

**Independent Test**: Classify a fixture containing read, write and ambiguous commands.

**Acceptance Scenarios**:

1. **Given** a command changes device state, **When** classification runs, **Then** it is mutating
2. **Given** evidence is insufficient, **When** classification runs, **Then** it is unknown and prohibited from execution

---

### User Story 3 - Plan only proven integrations (Priority: P2)

Potential read-only additions receive a value/risk/overlap assessment before any parser or wrapper is proposed.

**Why this priority**: Existing API 4028 and Vnish sources should not be duplicated without value.

**Independent Test**: Compare each read-only capability with current sources and identify gaps only.

**Acceptance Scenarios**:

1. **Given** Toolkit duplicates an existing reliable metric, **When** integration is assessed, **Then** it is not prioritized without measurable benefit
2. **Given** a new mutating operation is discovered, **When** inventory closes, **Then** it requires a separate future spec and explicit safety policy

### Edge Cases

- Help itself is unavailable or returns a non-zero code.
- Output contains installation paths, credentials or miner addresses.
- Version changes between inventory and implementation.
- A command name appears safe but documentation is ambiguous.
- Toolkit hangs or spawns a console window.

## Requirements

### Functional Requirements

- **FR-001**: Inventory MUST record Toolkit executable identity, version, discovery method and timestamp.
- **FR-002**: Only documented help, version or vendor-proven read-only discovery commands MAY run during inventory.
- **FR-003**: Every command MUST be classified read-only, mutating or unknown; unknown MUST be treated as mutating for execution policy.
- **FR-004**: Sanitization MUST remove credentials, tokens, real miner addresses and sensitive local paths from committed artifacts.
- **FR-005**: Every invocation MUST have a bounded timeout, captured exit code and no-window behavior on Windows.
- **FR-006**: The inventory MUST compare read-only capabilities with API 4028, Vnish and existing diagnostics to identify actual gaps.
- **FR-007**: No parser or production wrapper MAY be implemented before a stable sample and risk classification exist.
- **FR-008**: Existing production action scope MUST remain reboot and restart only.
- **FR-009**: Any newly proposed mutating capability MUST require its own future high-risk spec.
- **FR-010**: Inventory outputs MUST be reproducible and versioned by Toolkit version.

### Key Entities

- **ToolkitInstallation**: Executable, version and sanitized environment identity.
- **CommandCapability**: Command syntax, category, evidence and risk classification.
- **InvocationSample**: Sanitized args, output shape, timeout and exit behavior.
- **IntegrationCandidate**: Read-only gap, value, overlap and prerequisites.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every discovered command has exactly one risk classification and evidence reference.
- **SC-002**: No unknown or mutating new command is executed against miners.
- **SC-003**: Committed inventory artifacts contain no secrets or real addresses.
- **SC-004**: All approved discovery invocations terminate within their timeout without a visible console.
- **SC-005**: Any proposed integration identifies a current evidence gap and a separate implementation spec.

## Assumptions

- The locally installed Toolkit is the production-relevant version.
- Help/version invocation can be validated without touching miners; otherwise inventory is static/documentation-only.
- Current reboot/restart templates remain unchanged.

## Non-Goals

- Adding new Toolkit actions.
- Changing reboot/restart templates or confirmation.
- Reverse engineering undocumented protocols.
- Replacing API 4028 or Vnish collection.
