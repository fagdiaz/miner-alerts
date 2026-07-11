# Feature Specification: Miner Diagnostics And Interface Roadmap

**Feature Branch**: `feature/miner-diagnostics-interface-roadmap`

**Created**: 2026-07-11

**Status**: Draft

**Input**: Evaluate whether Miner Alerts should have a separate interface beyond Telegram, how to use Hashcore Toolkit features, how to collect and read Vnish logs, and how to identify conditions that avoid unnecessary S19j Pro reboots.

## User Scenarios And Testing

### User Story 1 - Diagnose Before Reboot (Priority: P1)

As the operator, I want the system to explain why a miner is unhealthy before rebooting so unnecessary reboots are avoided.

**Independent Test**: Review a LOW event and confirm the evidence includes signal freshness, board state, temperatures, pool state, firmware hints, and reboot gate result.

### User Story 2 - Read Vnish Evidence (Priority: P1)

As the operator, I want Vnish logs/events normalized into readable categories so I can tell whether firmware is tuning, restarting chains, or reporting a real hardware issue.

**Independent Test**: Import or inspect a Vnish log sample and classify events without triggering actions.

### User Story 3 - Evaluate A Separate Interface (Priority: P2)

As the operator, I want a local dashboard/report if it helps analysis more than Telegram, without adding a new unsafe action surface.

**Independent Test**: Produce a read-only report/dashboard proposal that does not expose secrets or reboot buttons.

## Requirements

- **FR-001**: Telegram remains the primary action interface until a separate UI has auth/local binding, audit logs, and confirmation.
- **FR-002**: Any separate interface starts read-only.
- **FR-003**: Vnish/firmware logs must be normalized into small events, not committed raw.
- **FR-004**: Hashcore Toolkit features must be inventoried as read-only or action before integration.
- **FR-005**: PSU/input voltage must be treated as data-source-dependent; if firmware does not expose it, use external PDU/UPS/smart meter evidence.
- **FR-006**: Sweet spot modeling must be descriptive before it becomes automated.

## Success Criteria

- **SC-001**: Roadmap identifies staged work for diagnostics, interface, Hashcore, Vnish, and power telemetry.
- **SC-002**: Reboot decision matrix separates observe, restart, and reboot.
- **SC-003**: Documentation makes clear which capabilities are known today and which require evidence.
