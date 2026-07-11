# Feature Specification: Miner Alerts Quality Hardening

**Feature Branch**: `feature/miner-alerts-quality-hardening`

**Created**: 2026-07-11

**Status**: Draft

**Input**: Improve Miner Alerts through quick wins and audits focused on false alerts, unnecessary reboots, logs, optimization, and Telegram bot development.

## User Scenarios And Testing

### User Story 1 - Reduce False Alerts (Priority: P1)

As the operator, I want alerts to reflect real miner conditions so transient or stale readings do not create unnecessary noise.

**Why this priority**: False alerts hide real incidents and reduce trust in the monitor.

**Independent Test**: Simulate or observe transient LOW/recovery behavior and verify that logs explain why an alert was or was not sent.

**Acceptance Scenarios**:

1. Given a miner briefly drops below threshold, when it recovers before the sustained window, then the system does not produce an escalation that implies sustained failure.
2. Given a stale snapshot or no data, when the bot reports status, then the output clearly distinguishes no-data from LOW.

### User Story 2 - Avoid Unnecessary Reboots (Priority: P1)

As the operator, I want auto-reboot to execute only after all safety gates pass so a restart of the monitor or stale state cannot reboot hardware unnecessarily.

**Why this priority**: A false reboot can disrupt mining and hide the original signal.

**Independent Test**: Start the monitor with old `state.json` LOW fields and verify no immediate auto-reboot occurs.

**Acceptance Scenarios**:

1. Given `state.json` contains old LOW markers, when the process starts, then startup sanitization and startup guard prevent immediate auto-reboot.
2. Given LOW is sustained in the current execution, when cooldown and window policies allow it, then auto-reboot can proceed according to policy.

### User Story 3 - Improve Telegram Operations (Priority: P2)

As the operator, I want Telegram commands to be click-safe, deterministic, and observable so manual intervention does not silently fail.

**Why this priority**: Telegram is an operational control surface for reboot/restart and diagnostics.

**Independent Test**: Run `/help`, `/status`, `/reboot`, `/rb<ID>`, `/reboot_no_ok`, `/c<code>`, and invalid confirm cases with debug flags enabled.

**Acceptance Scenarios**:

1. Given a click-safe reboot command, when the operator taps it, then the bot enters the existing confirmation flow.
2. Given an invalid or expired confirmation, when the operator submits it, then the bot replies with a clear message.
3. Given queue delivery fails before enqueue, when the request is a command, then logs show the fallback outcome.

## Requirements

### Functional Requirements

- **FR-001**: Changes MUST preserve existing state machine labels and transition meaning: OK, LOW, OFFLINE, HASHBOARD.
- **FR-002**: Auto-reboot changes MUST preserve QA guardrails, startup guard, sustained LOW, cooldown, and reboot window behavior.
- **FR-003**: Telegram dangerous actions MUST require confirmation.
- **FR-004**: Telegram command replies MUST be observable and must not be dropped by command dedupe/coalesce.
- **FR-005**: Logs for blocked reboots or delivery failures MUST identify the reason without exposing secrets.
- **FR-006**: Runtime config examples MUST stay production-safe and must not include real tokens or chat IDs.

## Success Criteria

- **SC-001**: `py_compile` passes after each code change.
- **SC-002**: QA validation shows no real action when `qa_allow_real_actions` is false.
- **SC-003**: Telegram command checks produce deterministic replies for valid and invalid inputs.
- **SC-004**: Evidence files record commands, logs, and unverified items.
