# Feature Specification: Vnish Log Intelligence

**Feature Branch**: `codex/016-vnish-log-intelligence`

**Created**: 2026-07-20

**Status**: Complete; production monitor rollout pending final controlled restart

**Input**: Collect the deployed Vnish log stream read-only, retain only bounded normalized operational events, and expose them in Telegram and the local dashboard without creating automatic actions.

## User Scenarios & Testing

### User Story 1 - Diagnose miner-side restarts (Priority: P1)

As an operator, I need firmware events such as watchdog restarts, chain faults, thermal protection, power warnings, pool failures, and normal autotune transitions classified consistently so I can distinguish normal Vnish work from incidents that need intervention.

**Why this priority**: The monitor currently sees symptoms from API 4028 but not the firmware reason that preceded a restart or hashrate drop.

**Independent Test**: Feed representative sanitized Vnish lines to the parser and verify deterministic category, severity, code, generated summary, timestamp, and fingerprint without retaining raw text.

**Acceptance Scenarios**:

1. **Given** a normal initialization/autotune line, **When** it is parsed, **Then** it is classified as a non-critical firmware transition.
2. **Given** chain-break/watchdog, thermal, power, fan, or pool failure evidence, **When** it is parsed, **Then** it receives the matching bounded category and severity.
3. **Given** an unknown or malformed line, **When** it is parsed, **Then** no event is invented.
4. **Given** a potentially sensitive raw line, **When** an event is stored, **Then** the database contains only generated summaries and a one-way fingerprint, not the raw line.

### User Story 2 - Collect logs safely and idempotently (Priority: P1)

As an operator, I need a native Windows CLI to read the confirmed Vnish WebSocket endpoints sequentially, with strict time/size limits and no miner mutation, so repeated collection is safe.

**Why this priority**: A parser without a proven acquisition path does not improve incident diagnosis.

**Independent Test**: Exercise the collector against a fake WebSocket client and the parser against a real-shaped sanitized payload; run a live read-only collection with bounded limits.

**Acceptance Scenarios**:

1. **Given** configured miners, **When** collection runs, **Then** it opens only `ws://<host>/api/v1/logs-ws/<tab>` and performs no POST or Hashcore action.
2. **Given** the same log history is collected twice, **When** it is persisted, **Then** the unique fingerprint prevents duplicate events.
3. **Given** timeout, refusal, oversized output, or missing dependency, **When** collection runs, **Then** it reports a bounded error and continues safely.
4. **Given** dry-run mode, **When** collection completes, **Then** no database row is written.

### User Story 3 - Read firmware evidence remotely (Priority: P2)

As an operator, I need `/firmware`, `/firmware all`, and `/firmware <miner>` plus a dashboard timeline to read stored firmware evidence without opening live connections from Telegram.

**Why this priority**: Telegram and the dashboard are the established operations surfaces.

**Independent Test**: Populate an isolated database with normalized events and verify bounded command/dashboard rendering with no miner IO or action call.

**Acceptance Scenarios**:

1. **Given** stored events, **When** `/firmware <miner>` is requested, **Then** it returns recent bounded evidence for that miner.
2. **Given** no stored events, **When** `/firmware` is requested, **Then** it explains how evidence becomes available without failing.
3. **Given** a generated dashboard, **When** firmware events exist, **Then** a bounded timeline shows category, severity, miner, source timestamp, and generated summary.

### Edge Cases

- WebSocket messages can arrive fragmented or contain multiple lines.
- Firmware timestamps have no guaranteed timezone and must not be silently treated as UTC.
- Old logs are replayed on every connection; deduplication is mandatory.
- One miner can be unreachable while others remain collectible.
- Unknown lines are ignored rather than stored as misleading incidents.

## Requirements

### Functional Requirements

- **FR-001**: Collection MUST be read-only and limited to the confirmed Vnish log WebSocket GET upgrade path.
- **FR-002**: The collector MUST process miners/tabs sequentially with configurable connect timeout, idle timeout, byte cap, and event cap.
- **FR-003**: Parsing MUST be pure, deterministic, bounded, and based on an explicit taxonomy.
- **FR-004**: Stored events MUST exclude raw log lines, pool credentials, user strings, and arbitrary firmware payloads.
- **FR-005**: Every event MUST have an idempotency fingerprint unique per miner/source tab.
- **FR-006**: Schema migration MUST be additive and preserve schema-v1/v2/v3 data.
- **FR-007**: The CLI MUST support dry-run and a configurable database path.
- **FR-008**: Telegram/dashboard reads MUST use SQLite only and perform no live miner IO.
- **FR-009**: Firmware events MUST NOT trigger reboot, restart, state changes, or notification policy in this version.
- **FR-010**: Runtime failures MUST degrade to explicit diagnostics without stopping the monitor.

## Key Entities

- **Vnish log event**: Collected timestamp, source timestamp text, miner identity, source tab, category, severity, code, generated summary, fingerprint.
- **Collection result**: Miner/tab status, received bytes, parsed count, inserted count, duplicate count, bounded error.
- **Firmware timeline**: Bounded read model for Telegram and dashboard.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Representative normal, chain, restart, thermal, power, pool/network, and fan lines classify with 100% deterministic test results.
- **SC-002**: Re-collecting identical logs creates zero duplicate rows.
- **SC-003**: No persisted event contains a raw source path, pool credential, or complete raw line.
- **SC-004**: Collection of one unreachable miner does not prevent processing subsequent miners.
- **SC-005**: Telegram and dashboard output remain bounded to configured limits and add zero miner requests.
- **SC-006**: Full tests, compilation, migration, live read-only smoke, and dependency checks pass before rollout.

## Assumptions

- Deployed Vnish 1.2.7 exposes unauthenticated read-only log streams on the local trusted network.
- `websocket-client` is an acceptable focused dependency for RFC 6455 framing and timeout handling.
- Log timestamps are displayed as firmware-local text until timezone provenance is known.
- Automatic policy consumption of firmware events is explicitly deferred pending production evidence.
