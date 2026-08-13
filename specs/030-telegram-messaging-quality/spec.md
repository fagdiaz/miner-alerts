# Feature Specification: Telegram Messaging Quality

**Feature Branch**: `codex/030-telegram-messaging-quality`

**Created**: 2026-08-13

**Status**: Complete / Uncommitted

**Input**: Optimize the complete Telegram messaging service using observed production messages, without changing miner state, polling or reboot policy.

**Risk Class**: MEDIUM

**Dependencies**: Spec 020 production closeout

## User Scenarios & Testing

### User Story 1 - Understand an alert immediately (Priority: P1)

An operator receives a compact Spanish alert that identifies what happened, which miners are affected, how long it has persisted, what changed, and where to inspect evidence.

**Why this priority**: Alerts are useful only when the operator can distinguish a new fault, a persistent fault, a recovery and an action failure without reconstructing several messages.

**Independent Test**: Render representative LOW, OFFLINE, board-loss, restart, recovery and auto-reboot-failure scenarios and verify one bounded actionable message per notification batch.

**Acceptance Scenarios**:

1. **Given** several miners become irregular within the grouping window, **When** notification is due, **Then** one message groups them with one line of current evidence and one click-safe detail reference per miner
2. **Given** an episode recovers, **When** recovery is confirmed, **Then** one message summarizes the bounded OK-to-OK sequence and duration
3. **Given** an automatic action fails, **When** the failure is delivered, **Then** the message identifies the miner, failed action and a read-only diagnostic path without implying success

---

### User Story 2 - Never lose a command response silently (Priority: P1)

An operator always receives a response or an explicit delivery error for every recognized command, even when messages are long or the normal sender queue is unavailable.

**Why this priority**: Silent command loss makes the monitor appear dead and can cause repeated dangerous requests.

**Independent Test**: Exercise normal queue, queue unavailable, queue pressure, oversized output and Telegram HTTP-error fixtures without miner or Hashcore access.

**Acceptance Scenarios**:

1. **Given** a recognized command produces a response longer than Telegram permits, **When** it is sent, **Then** it is split into ordered bounded parts with no content loss
2. **Given** the queue is unavailable, **When** a command replies, **Then** the bounded direct-send fallback runs once and records success or failure
3. **Given** notification pressure fills the queue, **When** a command reply arrives, **Then** it is not silently discarded or deduplicated

---

### User Story 3 - Discover only real, click-safe commands (Priority: P1)

An operator uses `/help` to see the commands and aliases that actually work, with safe actions clearly separated from confirmed actions.

**Why this priority**: The current help omits official click-safe reboot and confirmation aliases and mixes legacy/manual syntax with recommended commands.

**Independent Test**: Compare the help registry with normalized dispatcher commands and assert that every displayed click-safe token resolves to its documented handler.

**Acceptance Scenarios**:

1. **Given** the operator opens `/help`, **When** the index renders, **Then** it includes `/rb<ID>`, `/reboot_no_ok`, `/c<code>` and all supported read-only commands without unsupported CTAs
2. **Given** a dangerous command is listed, **When** it is rendered, **Then** it explicitly says that confirmation is required and does not execute from the help message
3. **Given** a legacy alias remains accepted, **When** help renders, **Then** that alias is not promoted as the official click-safe path

---

### User Story 4 - Preserve signal without Telegram noise (Priority: P2)

An operator receives new, persistent and recovered episode messages at the existing bounded cadence, while routine healthy status remains on demand.

**Why this priority**: Optimization must improve readability and delivery without reintroducing hourly healthy summaries or per-tick spam.

**Independent Test**: Replay grouped episodes and routine healthy ticks, then verify the existing 5/10/15/30/60/120-minute escalation and no unsolicited healthy status.

**Acceptance Scenarios**:

1. **Given** all miners remain healthy, **When** normal ticks complete, **Then** no periodic status message is sent unless explicitly configured
2. **Given** an irregular episode persists, **When** reminder ages are reached, **Then** due miners are grouped and no duplicate reminder is emitted
3. **Given** a command response resembles a notification, **When** both are sent, **Then** command delivery bypasses notification dedupe while notifications retain bounded coalescing

### Edge Cases

- A rendered event timeline exceeds Telegram's message-size limit.
- Multiple long command responses are requested quickly.
- Telegram returns non-200 after a message has been queued.
- The queue is missing or full while a command response is generated.
- A message contains a URL, token-like value, raw firmware payload or malformed Unicode.
- The service restarts while a notification batch is pending.
- A legacy command alias conflicts with an official click-safe token.

## Requirements

### Functional Requirements

- **FR-001**: User-facing messages MUST use a consistent taxonomy for alert, persistent fault, recovery, action result, command response and delivery error.
- **FR-002**: Every irregular episode notification MUST identify affected miner, current evidence, episode age, bounded sequence and click-safe detail reference when available.
- **FR-003**: Routine healthy fleet status MUST remain on demand by default; this feature MUST NOT add periodic healthy summaries.
- **FR-004**: Existing episode grouping and 5/10/15/30/60/120-minute then hourly reminder cadence MUST remain unchanged.
- **FR-005**: Every recognized command response MUST be marked as command delivery and MUST bypass notification dedupe/coalescing.
- **FR-006**: Messages that exceed the platform limit MUST be split deterministically at readable boundaries, preserve order and retain all content.
- **FR-007**: Queue-unavailable command fallback MUST remain bounded, use no automatic retries and emit unconditional outcome logs.
- **FR-008**: Queue pressure MUST NOT silently discard a command response; any discarded non-command notification MUST be explicitly logged with type and reason.
- **FR-009**: `/help` MUST be derived from one command registry and show only real supported commands and official click-safe aliases.
- **FR-010**: Official reboot CTAs MUST use `/rb<ID>`, `/reboot_no_ok`, `/c<code>` and `/confirm ...`; legacy aliases MAY remain accepted but MUST NOT be promoted.
- **FR-011**: Message text and delivery logs MUST redact Telegram credentials and MUST NOT include raw firmware payloads or secrets.
- **FR-012**: Telegram HTTP non-success and sender exceptions MUST remain visible in production logs without requiring debug flags.
- **FR-013**: Existing config files MUST remain compatible; safe behavior MUST not require editing local secrets.
- **FR-014**: State transitions, API 4028 polling, episode timing, auto-reboot gates, cooldowns, Hashcore calls and persistence semantics MUST remain unchanged.

### Key Entities

- **MessageEnvelope**: One bounded outbound message with category, delivery class, correlation metadata and text.
- **MessagePart**: Ordered fragment of an oversized envelope.
- **CommandMetadata**: Canonical command, official click-safe aliases, usage, summary and danger classification.
- **DeliveryOutcome**: Enqueued, sent, rejected, dropped or failed result with a non-secret reason.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All representative notification fixtures fit within the platform limit or split into ordered parts with byte-for-byte reconstructed content.
- **SC-002**: 100% of recognized command paths enqueue or directly attempt a response and none are subject to notification dedupe.
- **SC-003**: Every command displayed by `/help` resolves to an existing dispatcher path; all official click-safe aliases pass parser tests.
- **SC-004**: A replay of healthy ticks emits zero unsolicited status messages under production defaults.
- **SC-005**: Episode replay preserves the existing grouping and reminder schedule exactly.
- **SC-006**: Full regression, syntax, config, secret scan and action-policy invariants pass with no real miner action in QA.

## Assumptions

- Plain Telegram text remains the most robust production format; inline keyboards and callback queries remain out of scope.
- One authorized chat remains the operational destination.
- Existing SQLite event IDs remain the source for click-safe detail references.
- Delivery does not retry automatically; operators receive explicit logs for failed delivery.

## Non-Goals

- Changing state classification, thresholds, polling frequency or reboot decisions.
- Adding a web interface, webhook transport or a Telegram framework.
- Adding per-user preferences, quiet hours or multiple chat authorization.
- Replacing the Spec 021 liveness watchdog.
