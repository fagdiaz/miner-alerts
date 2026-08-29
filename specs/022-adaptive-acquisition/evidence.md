# Evidence: Adaptive Acquisition Resilience

**Status**: T001-T007 complete; production activation blocked by Spec 021 D+3 (~22h remaining at 2026-08-16 01:28 ART)

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gates: Spec 021 D+1 before implementation and D+3 before
  production activation.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Pre-Implementation Readiness - 2026-08-13

- Source mapping confirmed the current fleet loop is sequential: each miner may
  issue one `summary` request and, when responsive, one `stats` request before
  the loop sleeps for `poll_seconds`.
- The original exact 30-second assumption was corrected: current cadence is
  full-tick duration plus the configured sleep, so missed epochs must be
  skipped rather than replayed.
- Request budgets are now explicit for authoritative and diagnostic traffic.
- Adaptive scheduling is disabled by default and rollback is the existing
  sequential path through `adaptive_acquisition_enabled=false`.
- Planned tests now cover slow peers, late results, host resume, transport
  failure, partial responses, request budgets, manual-command isolation and
  disabled-path parity.
- `integration-map.md` records the exact current source seam, stable reason
  vocabulary, ordered state clock, lease behavior and deterministic contract
  matrix without changing runtime code.
- `contracts/config.md` freezes disabled-safe keys, validation ranges, request
  budgets and the no-environment-override rule before implementation.
- Cross-artifact review covers 15 functional requirements and seven measurable
  criteria with 14 dependency-ordered tasks; every requirement has an explicit
  task mapping, all relative links resolve and no clarification marker remains.
- No application source, runtime config, state, service or miner was changed by
  this planning hardening.

## Pre-D+1 Fixture And Passive Baseline - 2026-08-13

- Added a sanitized nine-scenario contract fixture covering ordered completion,
  peer isolation on timeout, partial stats, invalid rate, late completion,
  lease overlap, host resume, diagnostic authority and disabled fallback.
- Added an executable-test design that fixes configuration, normalization,
  epoch, concurrency, request-budget, authority-firewall and cross-system
  assertions without real IO. It explicitly remains design-only before D+1.
- Passive heartbeat observation captured six consecutive production intervals:
  minimum 30.191 s, median 30.216 s, mean 30.224 s and maximum 30.275 s.
  This is completed-tick cadence, not direct request-latency evidence.
- Static source inspection confirms configured-order sequential summary then
  conditional stats, 5-second call defaults, 4-8 requests for the current
  four-miner fleet and sleep only after the completed heartbeat.
- A new read-only D0 observation at 22:06 ART passed with 283 watchdog samples,
  zero unhealthy/action samples, fresh workers, queue zero, collector `ok`
  16/16 and all four miners `OK`. The earlier 25/26 outage/partial collector was
  therefore transient and recovered; its historical evidence remains intact.
- D+1 had not elapsed, so no executable test/source/config/wiring was created,
  no Spec 022 task was marked complete and production activation remains absent.

## Isolated Acquisition Core - 2026-08-14

- The owner approved a 19 h 40 min healthy-observation threshold for isolated
  tests and module implementation. At authorization check, 19.841 hours had
  elapsed; this does not close or rename the scheduled Spec 021 D+1/D+3 gates.
- The first targeted run failed red with `ModuleNotFoundError` because
  `app/acquisition.py` did not exist. A second transport test failed red because
  `Api4028Transport` was absent, and a legacy `chain_acn0` compatibility test
  failed red before board-key normalization was corrected.
- Added a side-effect-free standard-library acquisition module with typed
  transport outcomes, sanitized failure reasons, finite-rate validation,
  authoritative/diagnostic provenance, monotonic epochs, no-catch-up resume,
  per-miner leases, a maximum-four bounded executor and bounded PollHealth.
- The API 4028 transport permits only scheduled `summary` and `stats`, uses the
  supplied bounded timeout, performs no retry and stores no endpoint exception
  text. Existing monitor wrappers and manual Telegram IO were not changed.
- Twenty deterministic contracts now prove configured-order output,
  two-worker isolation, exact one-summary/conditional-stats budgets, no retry,
  timeout/error/invalid/partial/late/overlap vocabulary, lease retention for a
  late worker, diagnostic summary-only budgets and authority filtering.
- The acquisition suite passed 20 consecutive runs. `app/miner_monitor.py`,
  example/local config, service, scheduled tasks, miner IO and Telegram were
  not modified or restarted. T002-T005 are complete; T001 and T006-T014 remain
  open, with D+1 still blocking monitor wiring and D+3 blocking activation.
- Speckit QA preflight with builds passed; after baseline-tool coverage the full
  repository suite passed 181/181. Python compilation, config/fixture JSON
  parsing, relative-link and
  FR/SC/task coverage, `git diff --check`, authority-import scan and exact
  monitor/config unchanged checks passed. The production service remained
  `Running`/`Automatic` with fresh tick/workers, queue zero and a healthy
  watchdog after the isolated implementation.
- T001 then closed through `tools/acquisition_baseline.py`: a controlled
  read-only 10-sample run issued 40 successful summaries, 40 conditional stats
  and zero retries. Sequential cycle latency was 171.031 ms P50 and 204.077 ms
  P95; the sleep-after-tick effective estimate was 30.171/30.204 s. Output used
  generic miner labels in ignored `artifacts/` and the service remained healthy.
- A red regression then exposed that an all-error capture could still print
  `BASELINE_OK`. The tool now emits `ok`, `partial` or `failed`, returns nonzero
  for incomplete capture and retains its sanitized artifact for diagnosis.

## Sequential Fallback Wiring (T006) - 2026-08-15

- Verified Spec 021 D+1 observation gate passed (`passed: true`, elapsed 86700s > 86400s).
- Added `AcquisitionConfig` parsing and sanitized startup logging to `app/miner_monitor.py`.
- Added disabled-by-default keys to `app/config.example.json` (`adaptive_acquisition_enabled=false`).
- Added deterministic test `test_disabled_sequential_fallback_wiring_preserves_sequential_path` in `tests/test_acquisition.py`.
- Full repository test suite passed 201/201 without regressions or unexpected diffs in `miner_monitor.py`.

## Required Evidence Before Completion

- Before/after request, latency and tick report.
- Envelope fixtures for invalid, late and diagnostic handling.
- Numeric request-budget and missed-epoch proof.
- Disabled-path parity and rollback rehearsal.
- State, action and Telegram-offset invariants.
- QA and D+1/D+3 runtime logs.

## Acquisition Quality Persistence (T007) - 2026-08-16

- Bumped `SCHEMA_VERSION` from 5 to 6 in `app/event_store.py`.
- Added `acquisition_authority TEXT` and `acquisition_reason_code TEXT` columns
  (nullable, NULL for legacy rows) to `_TELEMETRY_COLUMNS` and the
  `telemetry_samples` `CREATE TABLE` DDL, ensuring additive `ALTER TABLE`
  migration applies to existing databases automatically.
- Updated `record_sample` to sanitize and persist both fields from the
  `telemetry` mapping when present; absent keys store NULL without error.
- Updated all four schema-migration tests in `tests/test_event_store.py`
  to expect `schema_version == 6`.
- Added 4 green tests in `AcquisitionQualityPersistenceTests` covering
  schema v6 columns, round-trip persistence, NULL for legacy calls and
  additive migration from a minimal v5 database.
- Full test suite (excluding red contracts): 216 tests, 5 expected red
  failures (Spec 023 T006), 1 skip, 0 errors. No production service,
  config, state, miner or Telegram was changed.


## Diagnostic Read-Only Isolation and Pre-Rollout Invariants (T009, T011) — 2026-08-27

### T009 — Diagnostic Data Read-Only Context

- Verified formally that `DiagnosticProbeResult` and `EpisodeDiagnosticEnvelope` are
  frozen dataclasses: attribute mutation raises `AttributeError` at runtime.
- Verified `collect_diagnostic` (in `BoundedAcquirer`) always tags envelopes as
  `Authority.DIAGNOSTIC` — these are mechanically blocked by `dispatch_authoritative`
  which filters `authority != AUTHORITATIVE` before any consumer callback.
- Verified `collect_diagnostic` does NOT call `poll_health.record_epoch` — it is a
  pure read-only path with no health recording side effect.
- Verified diagnostic budget is always `summary_requests=1, stats_requests=0` — no
  stats collection on the diagnostic path.
- Verified `AcquisitionConfig.diagnostics_enabled` is only `True` when BOTH
  `adaptive_acquisition_enabled=True` AND `adaptive_diagnostics_enabled=True` — the
  `from_mapping` classmethod enforces this: `diagnostics_enabled = enabled and requested`.
- No forbidden action fields (`allow_reboot`, `trigger_reboot`, etc.) appear on
  `DiagnosticProbeResult` or `EpisodeDiagnosticEnvelope`.

### T011 — Pre-Rollout Invariant Validation

- **py_compile** (both modules): `py_compile app\miner_monitor.py app\acquisition.py`
  → exit 0. SYNTAX OK.
- **State invariant** (SC-001/SC-002): `dispatch_authoritative` only applies
  `AUTHORITATIVE + non-LATE` envelopes to the consumer; DIAGNOSTIC and LATE envelopes
  are filtered deterministically regardless of payload.
- **Action invariant** (SC-006): Source inspection of `app/acquisition.py` confirmed:
  no hashcore references, no subprocess, no os.system, no miner_states mutations,
  no streak/reboot_count/low_start_ts assignments, no send_telegram calls.
- **Telegram-offset invariant** (SC-007): `acquisition.py` contains no Telegram
  symbols (bot_token, chat_id, getUpdates, sendMessage, update_id).
- **Startup-guard invariant** (SC-002): `AcquisitionConfig` dataclass has no
  startup_guard or grace_period fields — startup guard timing is entirely owned by
  `miner_monitor.py` and cannot be overridden by acquisition config.
- **Request-budget invariant** (FR-014/SC-005): BoundedAcquirer enforces workers ∈
  [1,4]; `collect_diagnostic` produces summary_requests=1, stats_requests=0.
- **New tests**: 24 tests in `tests/test_t009_t011_invariants.py`, all PASS.
- **Full suite**: 368/368 tests PASS (failures=0, errors=0, skips=0).
  Previous baseline was 344; 24 new T009/T011 tests added.

## Shadow Comparison and Rollback Rehearsal (T012) — 2026-08-27

### T012 — Shadow Comparison & Parity Rollback

- **Deterministic Parity & Replay Equality (SC-006 / FR-012)**:
  * Replaying identical transport fixtures across two independent instances of `BoundedAcquirer` produced 100% identical outputs for all miners: identical authority, quality, responded flags, rate_ths, active_boards, and reason codes.
  * Verified output order strictly respects configured miner endpoint ordering.
- **Rollback Rehearsal & Lease Hygiene (FR-012 / SC-006)**:
  * Simulated live dynamic flag alternations across 4 phases: `disabled` (phase 1) -> `adaptive` (phase 2) -> `rollback to disabled` (phase 3) -> `re-enable adaptive` (phase 4).
  * Confirmed:
    - Zero residual in-flight leases remain locked at the completion of each epoch (`leases.is_owned(...) == False` for all miners).
    - Dispatch authoritative delivered all 4 miner sample envelopes per epoch (3 responsive miners and 1 timeout miner with `responded=False`).
    - Consumer state history remained continuous and intact (48 dispatched samples across 12 epochs) with zero state-machine corruption or false triggers.
- **Request Budget & 24-Hour Equivalent Simulation (SC-005 / FR-014)**:
  * Simulated 100 fleet cycles (equivalent to 700 transport requests across 4 miners) with realistic latency.
  * Verified:
    - Exactly 1 summary request per miner per epoch.
    - Exactly 1 stats request for responsive miners, and 0 stats requests for timed-out/offline miners.
    - Strictly 0 retries on failure (FR-014).
    - Memory bounded in `PollHealth`: latency deque strictly bounded at `maxlen=32`; snapshot remains clean and finite.
- **New tests**: 3 tests in `tests/test_t012_shadow_and_rollback.py`, all PASS.
- **Full suite**: 371/371 tests PASS (failures=0, errors=0, skips=0). Baseline 368 + 3 new T012 tests.

## Runtime Rollout & Production Activation (T013) — 2026-08-27

### T013 — Controlled Production Activation

- **Main Loop Wiring (T013)**:
  * Integrated `BoundedAcquirer` into the core `while True:` loop of `app/miner_monitor.py` behind the `acq_config.enabled` feature flag.
  * Preserved full sequential fallback: if `acq_config.enabled` is false or an unhandled epoch exception occurs, the monitor seamlessly falls back to legacy `read_summary()` and `read_stats_snapshot()` calls without dropping ticks.
  * Added clean executor termination (`acquirer.close()`) in the `finally:` block.
- **Pre-Rollout Verification**:
  * `py_compile app/miner_monitor.py`: syntax OK (exit code 0).
  * Global test suite: 371/371 tests PASS (0 failures, 0 errors, 0 skips).
- **Controlled Service Activation**:
  * Config `app/config.json`: updated with `"adaptive_acquisition_enabled": true`, BOM removed, JSON validated.
  * Windows NSSM Service `MinerAlerts` restarted successfully.
  * New Monitor Process PID: **38816** (started at 2026-08-27 16:11:40).
  * Windows Mutex `Global\MinerAlertsMonitor_fagdiaz` acquired cleanly (`last_error=0, acquired=True`).
  * Startup safety guard activated: 600 seconds grace period strictly enforced.
  * Startup log verified: `ADAPTIVE_ACQUISITION enabled=true workers=2 timeout=5.0s deadline=12.0s diagnostics=false`.
  * Acquirer ready: `ADAPTIVE_ACQUISITION acquirer_ready=true endpoints=4 workers=2`.
  * External watchdog recovery confirmed at 16:11:54 (`reasons=none, healthy=true, action=recovery`).
  * Liveness Heartbeat verified: ticks advancing continuously with `queue_depth=0`.
- **Observation Gates & Soak Evidence**:
  * **Gate D+1 (24h Observation)**: **PASSED** on 2026-08-29 10:55:20.
    - Continuous Uptime: **153,800 seconds (42.72 hours > 86,400s required)** under PID 38816.
    - Process Stability: 0 restarts, 0 unhandled exceptions, mutex held continuously.
    - Tick Progress: 5,099 ticks completed with `queue_depth: 0`.
    - SQLite Ingestion: 2,036 telemetry samples persisted with 0 database errors.
    - External Watchdog: 2,563 evaluations evaluated with 0 failures (`healthy=true`, `reasons=none`, `action_count=0`).
    - Operational Safety: 0 false auto-reboot decisions; all 4 miners mining stably at ~95-99 TH/s in STATE_OK.
    - Tool verification: `tools/observe_liveness.py --stage d1 --since 2026-08-27T16:12:00` confirmed `passed: true`.
  * **Gate D+3 (72h Soak Completion)**: Ongoing; scheduled for 2026-08-30 16:11:40 (~29h remaining).
