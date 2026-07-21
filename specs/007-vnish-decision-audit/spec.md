# Feature Specification: Vnish Telemetry And Reboot Decision Audit

**Feature Branch**: `007-vnish-decision-audit`
**Created**: 2026-07-20
**Status**: Complete
**Input**: Persist normalized Vnish/S19j Pro telemetry and explain every relevant auto-reboot evaluation without changing action policy.

## User Scenarios & Testing

### User Story 1 - Understand Why A Miner Looked Unhealthy (Priority: P1)

As the operator, I want bounded historical evidence for each miner so that I can distinguish low hashrate from missing boards, temperature, hardware errors, tuning changes, or incomplete telemetry.

**Independent Test**: Feed representative Vnish `stats` payloads into the normalizer, persist the resulting sample, reopen the database, and verify each normalized field and diagnostic flag.

**Acceptance Scenarios**:

1. **Given** a Vnish response with three chain values, **When** it is normalized, **Then** the sample contains aggregate voltage, consumption, frequency, HW error, fan, and temperature evidence without storing the raw response.
2. **Given** a response with unknown or malformed fields, **When** it is normalized, **Then** unavailable values remain null and monitoring continues.
3. **Given** a multi-entry `STATS` response, **When** Vnish evidence is extracted, **Then** the parser inspects every dictionary entry and does not assume the first entry contains chain data.

---

### User Story 2 - Audit Every Auto-Reboot Outcome (Priority: P1)

As the operator, I want each meaningful auto-reboot evaluation recorded with its gate result and evidence so that I can prove why a reboot ran or was blocked.

**Independent Test**: Record decisions representing `not_low`, `invalid_signal`, `startup_guard`, `not_sustained`, `cooldown`, `window`, `qa`, `executed`, and `failed`, then query them newest-first by miner.

**Acceptance Scenarios**:

1. **Given** a LOW miner inside startup guard, **When** the existing policy blocks it, **Then** a decision row records `startup_guard` plus LOW duration and signal evidence.
2. **Given** cooldown or window blocks an action, **When** the existing branch exits, **Then** the corresponding remaining time or window count is persisted before that exit.
3. **Given** Hashcore succeeds or fails, **When** the existing action returns, **Then** the decision records `executed` or `failed` without changing the action call or its guards.

---

### User Story 3 - Ask The Bot Why No Reboot Happened (Priority: P2)

As the operator, I want a read-only Telegram diagnosis from local history so that I can understand the latest decision without triggering ASIC or Hashcore I/O.

**Independent Test**: Populate a temporary database, request `/why 23`, and verify a deterministic compact response assembled exclusively from SQLite.

**Acceptance Scenarios**:

1. **Given** a miner with decision history, **When** `/why <miner>` is requested, **Then** the latest gate result and relevant evidence are returned.
2. **Given** no miner argument, **When** `/why` is requested, **Then** the latest decision across miners is returned.
3. **Given** no matching history or unavailable storage, **When** `/why` is requested, **Then** the bot replies explicitly and performs no live network operation.

---

### User Story 4 - Produce A Local Incident Report (Priority: P2)

As the operator, I want a read-only report for a miner and time window so that Vnish evidence, state changes, restart incidents, and reboot decisions can be reviewed together.

**Independent Test**: Build a temporary database with samples/events/decisions and generate deterministic Markdown and JSON summaries without importing runtime config or contacting miners.

## Edge Cases

- `STATS` may be a dictionary, a list with a metadata entry first, or contain malformed values.
- Chain voltage and consumption are firmware-reported board-level hints; they must not be labeled as AC input voltage.
- A missing statistic must remain unknown rather than becoming zero.
- Event storage can be disabled or unavailable while monitoring and auto-reboot continue unchanged.
- Existing databases at schema v1 must migrate in place without deleting rows.
- An auto-reboot branch may `continue`; its audit record must be written before the existing exit.
- QA-forced signal changes must be visible in the decision evidence but must not permit real action unless the existing QA gate allows it.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST normalize Vnish telemetry using a pure, deterministic parser with no network or file I/O.
- **FR-002**: The parser MUST inspect all `STATS` dictionary entries and tolerate missing, malformed, scalar, or list values.
- **FR-003**: Normalized telemetry MUST include, when available: maximum temperature, average chain voltage, total chain consumption, average chain frequency, total chain HW errors, maximum fan RPM, fan PWM, and diagnostic flags.
- **FR-004**: Firmware-reported chain voltage MUST be described as chain/board voltage evidence and MUST NOT be presented as AC input voltage.
- **FR-005**: The monitor MUST reuse the `stats` response already needed by the polling cycle; this feature MUST NOT add a second `stats` request per miner tick.
- **FR-006**: SQLite schema migration MUST preserve schema-v1 samples/events and expose the resulting schema version.
- **FR-007**: Telemetry persistence MUST store normalized fields only and MUST NOT store complete raw ASIC responses, pool users, credentials, Telegram identifiers, or secrets.
- **FR-008**: The system MUST persist meaningful auto-reboot evaluations with the exact existing result: `not_low`, `invalid_signal`, `startup_guard`, `not_sustained`, `cooldown`, `window`, `qa`, `executed`, or `failed`.
- **FR-009**: Decision evidence MUST include the current signal/state, LOW elapsed time when applicable, board counts, normalized Vnish evidence, cooldown/window evidence, and QA/startup guard status when available.
- **FR-010**: Decision audit writes MUST occur before existing early exits and MUST NOT alter branch conditions, ordering, thresholds, timers, or Hashcore calls.
- **FR-011**: Storage errors MUST remain isolated from the monitor loop and be rate-limited through the existing event-store error channel.
- **FR-012**: `/why` and `/why <miner>` MUST read only local SQLite history and use command-delivery semantics.
- **FR-013**: A standalone report command MUST read the local database without loading `app/config.json`, contacting miners, or invoking Hashcore.
- **FR-014**: Retention MUST include reboot-decision rows and remain independently configurable with a production-safe default.
- **FR-015**: Existing state machine, startup guard, sustained LOW, cooldown, reboot window, QA, manual confirmation, polling offset, and notification behavior MUST remain unchanged.
- **FR-016**: No new runtime dependency, server process, dashboard, or container MUST be required for this feature.

### Key Entities

- **Vnish Telemetry**: Normalized board-level evidence extracted from API 4028 `stats` responses.
- **Reboot Decision**: A durable record of one meaningful evaluation in the existing auto-reboot policy path.
- **Diagnostic Flag**: A conservative evidence label such as `missing_board_signal`, `high_hw_errors`, or `telemetry_incomplete`; it never authorizes action.
- **Incident Report**: A local read-only correlation of telemetry, operational events, and reboot decisions for a bounded time window.

## Success Criteria

- **SC-001**: All supplied representative Vnish payloads normalize deterministically, including payloads where chain data is in `STATS[1]`.
- **SC-002**: An existing schema-v1 database migrates to schema v2 with all prior row counts and event IDs preserved.
- **SC-003**: Every existing auto-reboot blocked/executed branch listed in FR-008 has a deterministic persistence test and does not change the resulting action decision.
- **SC-004**: `/why` returns in under two seconds for the expected deployment and performs zero ASIC/Hashcore calls.
- **SC-005**: A 24-hour report for the current four-miner deployment completes locally in under two seconds at expected retention size.
- **SC-006**: Python compilation, unit tests, Speckit QA, config JSON validation, and diff checks pass.
- **SC-007**: The running Windows service is not restarted during implementation; activation is deferred to the explicit end-of-day release step.

## Assumptions

- Current Vnish payloads expose chain voltage in values around 12,000-13,500 and consumption around 800-950 per chain; units are kept explicit and conservative in documentation.
- Pool health, firmware version, and raw Vnish logs remain follow-up work because collecting them in the production loop would add network I/O not already required by state evaluation.
- SQLite remains the appropriate operational store at current scale; a dashboard/API should consume this stable schema in a later feature.
