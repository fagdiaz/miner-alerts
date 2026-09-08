# Feature Specification: Daily Executive Digest (Spec 034)

**Feature Branch**: `codex/034-daily-executive-digest`  
**Created**: 2026-09-07  
**Status**: Ready / SpecKit Active  
**Input**: Telegram Max Initiative (V3 Expansion Plan) — Scheduled morning executive digest (e.g. 08:00 AM) and on-demand `/digest` command summarizing 24-hour fleet uptime, average TH/s vs nominal, energy efficiency (J/TH), mining shares quality, operational incidents/reboots, and SQLite backup integrity status.  
**Risk Class**: LOW-MEDIUM (Read-only analytical queries, scheduled timer/scheduler check, Telegram delivery)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain logic, data models, aggregation math, scheduling checks, and comprehensive test suite).  

---

## User Scenarios & Testing

### User Story 1 - Scheduled Morning Executive Briefing (Priority: P1)

Every morning at a scheduled local time (default: 08:00 AM Argentina Time, UTC-3), the mine operator receives a concise, beautifully formatted summary of the preceding 24 hours directly in Telegram.

**Why this priority**: Eliminates the need for the operator to log into dashboards or run manual diagnostic commands every morning. In a 5-second glance, the operator verifies that all miners ran at full speed, efficiency was maintained, and backups were executed.

**Independent Test**: Simulate time progression crossing the 08:00 threshold; verify that the daily digest is generated and dispatched exactly once per calendar day; assert that subsequent ticks on the same day do NOT duplicate the notification.

**Acceptance Scenarios**:
1. **Given** `daily_digest_enabled: true` and local time crosses 08:00 AM, **When** the monitoring evaluation loop runs, **Then** an executive digest covering the past 24 hours is sent to the configured Telegram chat.
2. **Given** the digest has already been sent for today (`last_daily_digest_date == today`), **When** subsequent evaluation ticks occur, **Then** no duplicate digest is emitted.
3. **Given** the monitor process restarts during the day, **When** `state.json` is loaded, **Then** `last_daily_digest_date` is preserved, preventing duplicate dispatch.

---

### User Story 2 - On-Demand Executive Digest via `/digest` (Priority: P1)

At any time of day, an operator or investor types `/digest` (or `/summary`) in Telegram to receive the real-time 24-hour aggregate report immediately.

**Why this priority**: Instant operational auditing before team syncs or after resolving power/network maintenance.

**Independent Test**: Execute `/digest` command via mock update dispatcher; assert valid formatted summary with fleet metrics is sent within 1.5 seconds.

**Acceptance Scenarios**:
1. **Given** active telemetry samples in SQLite, **When** the operator sends `/digest`, **Then** the bot replies with the 24h summary including uptime %, average TH/s, nominal comparison, J/TH, shares %, and incident count.

---

### User Story 3 - Comprehensive Fleet Metrics & Health Aggregation (Priority: P1)

The digest aggregates telemetry and operational evidence across multiple dimensions:
- **Uptime Flota**: % of samples in OK state over 24h + ratio of currently active vs configured miners.
- **Hashrate Promedio**: Average total TH/s vs fleet nominal threshold.
- **Eficiencia Energética**: Calculated ratio of Watts / (TH/s) = Joules per Terahash (J/TH).
- **Calidad de Minado**: Accepted shares %, rejected shares %, hardware error counts.
- **Incidentes Operativos**: Count of warning/critical events and reboot decisions in 24h.
- **Estado del Backup**: Timestamp, size, and SHA-256 verification of the latest SQLite backup.

**Acceptance Scenarios**:
1. **Given** 4 active S19j Pro miners, **When** aggregated, **Then** the metrics reflect mathematically correct averages and ratios across the window.
2. **Given** zero samples or missing backup directory, **When** aggregated, **Then** the engine produces graceful fallback values (e.g. `N/D`, `Sin backups recientes`) without crashing.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support command `/digest` (and alias `/summary`):
  - Generates and replies with the 24h executive digest text.
  - Registered in `CMD_WHITELIST`, `_COMMANDS`, and `/help`.
- **FR-002**: System MUST support scheduled morning dispatch:
  - Configuration keys:
    - `"daily_digest_enabled"`: boolean (default `true`).
    - `"daily_digest_time"`: string `HH:MM` in 24h format (default `"08:00"`).
  - Evaluated on each tick against Argentina local time (UTC-3).
  - Emits exactly once per calendar date (`YYYY-MM-DD`).
  - Tracks and persists `last_daily_digest_date` in `app/state.json`.
- **FR-003**: Digest engine MUST query SQLite in read-only mode (`?mode=ro`):
  - Aggregates samples between `(now_ts - 86400)` and `now_ts`.
  - Calculates fleet uptime %, average hashrate, efficiency (J/TH), and shares quality.
  - Queries `operational_events` and `reboot_decisions` for 24h incident count.
  - Queries `backups/` or backup root for latest verified backup manifest and integrity.
- **FR-004**: Digest text MUST follow the standard executive card format with emojis, section dividers, and bold metrics.

### Non-Functional & Safety Requirements

- **NFR-001**: Read-only SQLite isolation: zero locks or transaction interference with the live monitor writer.
- **NFR-002**: Execution speed: 24h aggregation query must complete in < 200ms on a 25 MB database.
- **NFR-003**: Zero disruption to running production monitor PID 38816.

---

## Success Criteria

- **SC-001**: `/digest` generates and delivers the full report in < 1.0 second.
- **SC-002**: Scheduled dispatch fires reliably at 08:00 AM with zero duplicate sends per day.
- **SC-003**: 100% unit and integration test coverage across aggregation, scheduling, and formatting with zero regressions.
