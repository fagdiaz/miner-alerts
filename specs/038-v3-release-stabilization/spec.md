# Feature Specification: V3 Core Concurrency, Multi-Threading Race Conditions & Release Stabilization

**Feature Branch**: `codex/038-v3-release-stabilization`  
**Created**: 2026-09-07  
**Status**: DRAFT / READY FOR CLAUDE SONNET 4.6 (THINKING)  
**Assigned Engine**: **Claude Sonnet 4.6 (Thinking)** (Multi-threading, mutex coordination, queue concurrency & FSM race conditions)  
**Risk Class**: HIGH (Direct touchpoint with production concurrency, socket timeouts, Windows mutexes, queue worker coordination)

---

## 1. Context & Business Need

Between Specs 031 and 037, seven major capabilities were integrated into `miner_monitor.py`:
1. **Spec 031**: Telegram Interactive Callbacks (`callback_query` polling, worker queue, inline keyboard reboots).
2. **Spec 032**: Telegram Visual Charts (`send_photo`, in-memory PNG generation).
3. **Spec 033**: Miner Maintenance Snooze (`/snooze`, state persistence, auto-reboot suppression).
4. **Spec 034**: Daily Executive Digest (Scheduled daily digest worker, once-per-day guard).
5. **Spec 035**: Cooling & Fan Health Intelligence (`/fans`, cooling streak, alert evaluation).
6. **Spec 036**: Hashrate Efficiency Tracking (`/efficiency`, J/TH calculation, efficiency streak).
7. **Spec 037**: Vnish Presets & Autotuning Tracking (`/presets`, downclock detection, baseline frequency).

While each pure domain module operates flawlessly and passes 495 tests, the integration points in `miner_monitor.py` span multiple asynchronous boundaries:
- The main telemetry polling loop (`_poll_miners_concurrent` / adaptive acquisition workers).
- The Telegram polling loop (`_telegram_worker` / `_telegram_poller` / long polling).
- The Telegram message sender queue (`_send_telegram_worker`).
- The scheduled tasks (Daily Digest 08:00 AM dispatcher).
- State read/write access to `MinerState` fields across threads.

To certify the **Release Candidate V3 (v3.0.0)** with zero risk of production deadlock or spurious reboots, an authoritative multi-threading concurrency audit and race-condition hardening pass must be executed by **Claude Sonnet 4.6 (Thinking)**.

---

## 2. User Scenarios & Verification Targets

### User Story 1: Lock Consistency & Shared State Protection (Priority: P0)
**Given** the main monitor loop evaluates cooling, efficiency, downclock, and snooze states,  
**When** an operator concurrently invokes Telegram commands (`/status`, `/snooze`, `/fans`, `/efficiency`, `/presets`, `/digest`) or taps inline callback buttons,  
**Then** all reads and writes to `MinerState` attributes MUST be atomic and protected by `state_lock`, preventing race conditions, stale streak reads, or corrupted `state.json` serializations.

### User Story 2: Non-Blocking Telegram Queue & Callback Deadlock Immunity (Priority: P0)
**Given** an operator rapidly taps multiple inline callback buttons (e.g. reboot request, cancel, chart request),  
**When** the Telegram outbound queue is busy sending a large PNG chart or multiple message chunks,  
**Then** `answer_callback_query` MUST respond within 3 seconds without blocking on the queue or starving telemetry loops, and callback tokens (`rb_req`, `rb_cfm`) MUST be strictly single-use and race-immune.

### User Story 3: SQLite Concurrency & Read-Only Lock Immunity (Priority: P1)
**Given** the production monitor process (`PID 38816`) writes continuous telemetry samples and events to `data/miner_alerts.db`,  
**When** analytical commands (`/chart`, `/digest`, `/fans`, `/efficiency`, `/presets`) or the UI server (`task-867`) perform complex multi-miner reads,  
**Then** all queries MUST strictly use `file:...mode=ro` with bounded connection timeouts (<= 2.0s) and guaranteed `finally: conn.close()`, guaranteeing ZERO write lock starvation on the live database.

### User Story 4: Auto-Reboot Interlock & Snooze Integrity (Priority: P0)
**Given** a miner is degraded or experiencing thermal throttling,  
**When** the operator activates `/snooze <miner> <minutos>`,  
**Then** the auto-reboot evaluation MUST immediately abort without issuing reboots, even if an auto-reboot decision was concurrently being formed in the acquisition tick.

---

## 3. Scope & Non-Goals

### In Scope:
- `miner_monitor.py`: Audit `state_lock` synchronization around new V3 state fields.
- `miner_monitor.py`: Audit Telegram worker queues, callback query dispatcher, and timeout bounds.
- Concurrency test suite: `tests/test_v3_concurrency.py` simulating high-concurrency contention between commands, callbacks, and polling loops.
- SQLite connection hygiene across all V3 modules.
- Verification that live production process `PID 38816` remains 100% undisturbed.

### Out of Scope:
- Modifying core hashing algorithms or ASIC hardware settings.
- Modifying existing command syntax or output formats.
- Adding new user-facing features (feature freeze for V3 Release Stabilization).
