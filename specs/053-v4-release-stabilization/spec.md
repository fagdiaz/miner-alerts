# Feature Specification: V4 Core Governance Concurrency, Multi-Threading Hardening & Release Stabilization

**Feature Directory**: \specs/053-v4-release-stabilization\  
**Created**: 2026-09-10  
**Status**: DRAFT / IN IMPLEMENTATION  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain analysis, concurrency stress suite, Mobile-First card validator, and release certification)  
**Risk Class**: HIGH (Validates production concurrency, mutex coordination, callback dispatchers, and full regression baseline)

---

## 1. Context & Business Need

Between Specs 039 and 052, 14 major capabilities and governance systems were integrated into the \miner-alerts\ codebase:
1. **Spec 039**: Closed-loop Vnish Fan Governor (modulating fans to 82.0°C target with fail-safe at 100% PWM).
2. **Spec 040**: Dynamic Voltage Presets & Voltage Elevator Autodiscovery (per-group load balancing).
3. **Spec 041-042**: Modular Subpackage Reorganization (\pp/governance\, \pp/hardware\, \pp/reporting\, \pp/common\) and 22-shim purge.
4. **Spec 043**: Interactive Command Center (\/menu\ with in-place navigation and RBAC protection).
5. **Spec 044**: Silent Mode & Thermal Guard (bounded acoustic limits 40%-70% with 83.5°C emergency spike release).
6. **Spec 045**: Interactive Mobile Help Center (\/help\ categorical directory).
7. **Spec 046**: Mobile Card Layouts C1-C10 (\/status\, \/fans\, \/efficiency\, \/presets\ <= 32 cols).
8. **Spec 047**: Mobile Balancer, Elevadores, Digest, Snoozed & Events Cards.
9. **Spec 048**: Safe Fleet Shutdown & Electrical Maintenance Selection Bitmask.
10. **Spec 049**: Active Thermal Purge Ramp (100% duty for 45s, acoustic drop to 40% PWM idle floor).
11. **Spec 050**: Post-Blackout Recovery Guard (proactive stopped-state detector with 1-tap fleet resume).
12. **Spec 051**: Fast Phase Drop vs Connectivity Discriminator (<3s immediate trip classification).
13. **Spec 052**: Scheduled Electrical Maintenance Windows & Soft Pre-Ramp Planner (T-10m, T-5m, T-0).

### Concurrency & Multi-Threading Surface
While each individual domain module passes its isolated tests (781 tests total), the main loop in \miner_monitor.py\ now coordinates multiple asynchronous and multi-threaded touchpoints:
- **Telemetry Polling Thread**: Reads and mutates \states: Dict[str, MinerState]\, executes the governor, balancer, post-blackout watchdog, phase drop discriminator, and maintenance scheduler cycles.
- **Telegram Polling Thread**: Handles incoming commands (\/menu\, \/status\, \/schedule_maintenance\, \/shutdown_fleet\) and concurrent inline callback queries (\shut:*\, \pbr:*\, \sch:*\, \menu:*\, b:*\, \snz:*\).
- **Telegram Outbound Sender Worker**: Processes priority queue messages (\HIGH\, \DEFAULT\, \LOW\) and fallback sends.
- **State Persistence Worker**: Periodically serializes \state.json\ (\states\, \scheduled_maintenance\, \silent_mode\, \pbr_watchdog\) while memory is concurrently modified.
- **SQLite Concurrency**: Multiple readers querying \data/miner_alerts.db\ in WAL mode.

To certify the **Release Candidate V4 (v4.0.0)**, we must execute an exhaustive concurrency audit, create a deterministic stress suite, certify 100% compliance of all mobile cards against the 32-column standard, and verify zero regressions across the entire project.

---

## 2. User Stories & Verification Targets

### User Story 1: Lock Consistency & Shared State Protection (Priority: P0)
**Given** the main monitor loop runs periodic governance cycles (fan governor, balancer, post-blackout guard, maintenance scheduler),  
**When** an operator concurrently issues Telegram commands or triggers callback buttons,  
**Then** all shared state dictionaries (\states\, \_ACTIVE_SCHEDULED_WINDOW\, \_SILENT_MODE_EXPIRY_TS\, \_POST_BLACKOUT_WATCHDOG\) MUST be protected by \state_lock\ or atomic snapshotting, preventing race conditions or dictionary iteration crashes during \save_state()\.

### User Story 2: Non-Blocking Callback Dispatchers & Queue Deadlock Immunity (Priority: P0)
**Given** an operator rapidly taps inline buttons (\shut:toggle:*\, \pbr:resume:fleet\, \sch:cancel:*\),  
**When** the Telegram outbound queue is saturated or experiencing backoff,  
**Then** callback responses and background action dispatchers MUST never deadlock the Telegram polling thread or block the main telemetry cycle.

### User Story 3: Global Mobile-First Compliance (Priority: P0)
**Given** all 15+ Telegram card generators across the system,  
**When** evaluated with representative production data,  
**Then** 100% of generated lines MUST strictly comply with \isible_line_width(line) <= 32\ without any visual clipping or awkward wrapping.

### User Story 4: Release Candidate V4 Certification (Priority: P0)
**Given** the complete project test suite with 781 existing tests,  
**When** executed alongside the new V4 concurrency and mobile compliance suites,  
**Then** 100% of tests MUST pass cleanly (0 errors, 0 failures), proving zero regression and certifying Release Candidate V4 (v4.0.0).

---

## 3. Scope & Non-Goals

### In Scope:
- \miner_monitor.py\: Audit \state_lock\ synchronization and atomic snapshots across all V4 additions.
- \miner_monitor.py\: Audit callback query dispatchers and thread pooling.
- Concurrency test suite: \	ests/test_v4_concurrency.py\ simulating high-concurrency contention across all V4 systems.
- Mobile compliance test suite: \	ests/test_mobile_compliance.py\ validating all cards against \isible_line_width <= 32\.
- Full project regression test pass.
- Release documentation: \DEVELOPMENT_LOG.md\, \ROADMAP.md\, and \SPEC_PROGRAM.md\.

### Out of Scope:
- No changes to API 4028 network protocol.
- No modifications to external PDU/UPS hardware integrations (remains blocked_external).
