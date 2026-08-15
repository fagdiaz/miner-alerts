# Miner Alerts Speckit Roadmap

**Last reviewed**: 2026-08-15
**Specification program**: `docs/speckit/SPEC_PROGRAM.md`
**Delivery calendar**: `docs/speckit/DELIVERY_PLAN.md`

## Operating Goal

Miner Alerts is the operations and diagnosis layer for S19j Pro miners. Work is
ordered to detect real failures, avoid unsafe or unnecessary actions, preserve
trustworthy evidence, recover the monitor itself, and only then add optional
interfaces or integrations.

## Current Baseline

- Windows service with one mutex-protected monitor/action authority.
- API 4028 authoritative polling, normally every 30 seconds.
- Telegram Bot API long polling as the remote command/control interface.
- Bounded read-only Vnish WebSocket log collection as complementary firmware
  evidence, never the sole health or action source.
- SQLite schema v5 for telemetry, operational events, reboot decisions,
  firmware evidence and collector health.
- Read-only static operations dashboard and incident reports.
- Auto-reboot gates for finite/current signal, sustained LOW, startup, thermal,
  fleet, Vnish transition, cooldown, window and QA safety.
- Spec 020 is committed/pushed and runtime-closed as `e502ab9`. Spec 030
  messaging quality is committed/pushed as `2afd65e` and active in production.
  Spec 021 liveness is activated and its D+1 observation gate passed (86,700s > 86,400s).
  Spec 022 has completed T006 sequential fallback wiring and compact Telegram UX formatting
  behind `adaptive_acquisition_enabled=false`, with 206/206 passing tests.

## Architecture Direction

1. API 4028 polling remains authoritative because the deployed endpoint is
   request/response and has no proven health push contract.
2. Vnish WebSockets remain bounded and read-only for asynchronous firmware
   evidence.
3. An independent watchdog supervises process, tick and worker progress; a
   protocol change cannot replace monitor liveness supervision.
4. Acquisition may use bounded concurrency, but only one 30-second
   authoritative envelope per miner may update state/action semantics.
5. Prometheus/Grafana are the preferred optional observability stack. They read
   sanitized snapshots and cannot trigger actions.
6. Docker is limited to auxiliary observability. The monitor and Hashcore remain
   Windows-native.
7. Electrical protocol selection follows real hardware discovery. No AC voltage
   is inferred from hashboard telemetry.
8. FastAPI is conditional after static HTML and Grafana are measured. Web
   actions and remote exposure are excluded.
9. OpenTelemetry, broker-only MQTT and continuous Vnish workers remain deferred
   until concrete prerequisites exist.

## Delivery Queue

| Order | Work package | Status | Priority | Risk | Target |
| --- | --- | --- | --- | --- | --- |
| Gate | Spec 020 episode-alerts closeout | COMPLETE | P0 | HIGH | Closed 2026-08-13 |
| Hotfix | Spec 030 Telegram messaging quality | COMPLETE | P0 | MEDIUM | Closed 2026-08-13 |
| 1 | Spec 021 monitor-liveness-watchdog | ACTIVATED / OBSERVATION PENDING | P0 | HIGH | 2026-08-13 to 2026-08-17 |
| 2 | Spec 022 adaptive-acquisition | IN PROGRESS / ISOLATED | P1 | HIGH | Started 2026-08-14; wiring after 021 D+1 |
| 3 | Spec 023 incident-evidence-fusion | PLANNED | P1 | MEDIUM | 2026-09-11 to 2026-09-24 |
| 4 | Spec 024 electrical-source-discovery | PLANNED / CONDITIONAL | P1 | MEDIUM | 2026-09-25 to 2026-10-05 |
| 5 | Spec 025 prometheus-metrics | PLANNED | P1 | MEDIUM | 2026-10-06 to 2026-10-19 |
| 6 | Spec 026 hashcore-capability-inventory | PLANNED | P2 | MEDIUM | 2026-10-20 to 2026-10-29 |
| 7 | Spec 028 backup-retention-restore | PLANNED | P1 | HIGH | 2026-10-30 to 2026-11-12 |
| 8 | Spec 027 operator-interface-decision | PLANNED / CONDITIONAL | P2 | MEDIUM | 2026-11-13 to 2026-11-26 |
| 9 | Spec 029 v2-release-stabilization | PLANNED | P0 | HIGH | 2026-11-27 to 2026-12-20 |

Dates include implementation plus the separate review/fix gate detailed in
`DELIVERY_PLAN.md`. Runtime evidence can move dates but cannot compress gates.

## Work Packages

### R0 - Close Spec 020 Production Activation (`COMPLETE`, P0)

**Spec**: `specs/020-episode-alerts`
**Target**: 2026-08-13 to 2026-08-17

- [x] Implement grouped episodes and escalating reminders.
- [x] Eliminate positive-hashrate plus OFFLINE status contradictions.
- [x] Add persisted click-safe episode detail.
- [x] Commit and push `e502ab9`.
- [x] Prove the deployed `e502ab9` PID/code/config and startup-guard evidence
  from the 2026-08-06 service activation.
- [x] Smoke current API 4028/status rendering and persisted event detail locally.
- [x] Activate Telegram token-log redaction through an elevated NSSM restart;
  verify the new startup block and zero new token occurrences.
- [x] Rotate the token previously present in the old ignored local log and
  restart once with the new local credential.
- [x] Smoke `/status`, `/events` and `/e<ID>` from the authorized Telegram chat.
- [x] Re-prove startup persisted LOW cannot cause immediate auto-reboot.
- [x] Complete the observation gate with no open P0/P1 regression.

**Exit**: Spec 020 T020 and evidence close. No duplicate Spec 021 is created for
this work.

### R0.5 - Telegram Messaging Quality (`COMPLETE`, P0)

**Spec**: `specs/030-telegram-messaging-quality`

- [x] Bounded UTF-8-safe splitting below the Telegram text ceiling.
- [x] Command-aware queue admission with bounded direct fallback under pressure.
- [x] Explicit queue drop/bypass outcomes without logging message payloads.
- [x] Central help aligned with `/rb<ID>`, `/reboot_no_ok` and `/c<code>`.
- [x] Preserve episode cadence, notification dedupe and all action-policy gates.
- [x] Complete one elevated NSSM restart and read-only Telegram smoke.

**Invariant**: no state, polling, threshold, cooldown or Hashcore decision change.

### R1 - Monitor Liveness And Recovery (`ACTIVATED / OBSERVATION PENDING`, P0)

**Spec**: `specs/021-monitor-liveness-watchdog`

Its implementation, deterministic no-action validation, elevated Windows
activation and controlled SCM recovery proof are complete. D+1/D+3 remain open.

- [x] Atomic versioned heartbeat after completed fleet ticks.
- [x] Independent service/process/tick/Telegram-worker/collector assessment.
- [x] Hidden Windows watchdog definition with bounded notification dedupe.
- [x] Install the hidden task and configure SCM recovery with rollback export.
- [x] Deterministic kill, hang and stale-worker classification with no action authority.
- [x] Prove the activated PID, mutex, startup guard and fresh scheduled heartbeat.
- [x] Prove SCM recovery firing with a new PID, mutex, startup guard and heartbeat.
- [ ] Complete D+1/D+3 observation.

**Invariant**: no second monitor and no miner/Hashcore access from the watchdog.

### R2 - Acquisition Resilience (`IN PROGRESS / ISOLATED`, P1)

**Spec**: `specs/022-adaptive-acquisition`

**Readiness**: planning hardened against the current sequential request path.
After an owner-approved 19 h 40 min healthy observation, isolated tests and the
pure module began on 2026-08-14. Monitor wiring waits for Spec 021 D+1 and
production activation waits for Spec 021 D+3.

- [x] Pure typed authoritative/diagnostic envelope and epoch contracts.
- [x] Bounded executor, lease and peer-isolation contracts without runtime wiring.
- [x] Explicit valid/partial/invalid/timeout/error/late quality normalization.
- [x] Sequential request/count/latency baseline with sanitized ignored output.
- [ ] Optional diagnostic recovery probes that cannot update state or actions.
- [ ] Baseline/shadow comparison for latency, requests, sample age and alerts.

**Invariant**: thresholds, hysteresis, polling offset and action policy unchanged.

### R3 - Incident Evidence Fusion (`PLANNED`, P1)

**Spec**: `specs/023-incident-evidence-fusion`

- [ ] Normalize persisted episode, Vnish, quality, pool, action and fleet facts.
- [ ] Build stable per-miner historical baselines from eligible samples.
- [ ] Separate observed, suspected and confirmed conclusions.
- [ ] Show supporting, contradicting and missing evidence.
- [ ] Persist versioned assessments for deterministic replay.

**Invariant**: assessments are advisory and never authorize actions.

### R4 - Electrical Source Discovery (`PLANNED / CONDITIONAL`, P1)

**Spec**: `specs/024-electrical-source-discovery`

- [x] Establish that miner chain voltage is not AC input voltage.
- [ ] Inventory actual PSU/PDU/UPS/meter model and documented telemetry.
- [ ] Select at most one read-only SNMPv3, Modbus TCP, vendor HTTPS or
  real-publisher MQTT adapter after the source gate.
- [ ] Normalize units, source time, quality and collection health.
- [ ] Correlate power facts conservatively with incidents.

**Exit**: supported adapter with evidence, or explicit blocked hardware result.
No protocol writes and no power-driven action.

### R5 - Prometheus Metrics And Grafana (`PLANNED`, P1)

**Spec**: `specs/025-prometheus-metrics`

- [ ] Atomic sanitized metrics snapshot from the native monitor.
- [ ] Separate `prometheus_client` exporter with bounded cardinality.
- [ ] Optional pinned Docker Compose Prometheus/Grafana stack.
- [ ] Local-only fleet, freshness, liveness, episode and delivery dashboards.
- [ ] Redaction, resource, series-count and outage-isolation proof.

**Invariant**: metrics are not canonical history and never trigger actions.

### R6 - Hashcore Capability Inventory (`PLANNED`, P2)

**Spec**: `specs/026-hashcore-capability-inventory`

- [x] Establish static planning baseline: Toolkit `1.6.0+167`, wrapper/executable
  present and pass-through wrapper shape, without process execution.
- [ ] Implement metadata-only inventory as the zero-process default.
- [ ] Run only exact fingerprint-bound vendor-proven help/version discovery with
  timeout/no-window; current allowlist is empty and invocation is blocked.
- [ ] Classify every operation read-only, mutating or unknown.
- [ ] Compare read-only capabilities with API 4028/Vnish overlap.
- [ ] Require a new high-risk spec for every future action.

**Invariant**: production action scope remains existing reboot/restart only.

### R7 - Backup, Retention And Restore (`PLANNED`, P1)

**Spec**: `specs/028-backup-retention-restore`

- [ ] SQLite online backup with atomic promotion and SHA-256 manifest.
- [ ] Path-guarded 14 daily / 8 weekly / 12 monthly retention.
- [ ] Hidden non-overlap Scheduled Task and free-space guard.
- [ ] Restore only to staging with checksum, integrity, schema and row checks.
- [ ] One production backup plus successful staging restore drill.

**Invariant**: never copy a live `.db` blindly and never overwrite production
automatically.

### R8 - Operator Interface Decision (`PLANNED / CONDITIONAL`, P2)

**Spec**: `specs/027-operator-interface-decision`

- [ ] Score real workflows across Telegram, static HTML and Grafana.
- [x] Baseline the existing SQLite `mode=ro` static generator and its safety tests.
- [ ] Require three consecutive fixed P1 workflow runs after Specs 025/028.
- [ ] Close no-build when current interfaces meet P1 targets.
- [ ] Only if a gap remains, build a loopback FastAPI read-only MVP.
- [ ] Add HTMX/server rendering only for approved filtering/refresh.
- [ ] Reject config, miner proxy, reboot, restart and confirm web routes.

**Invariant**: Telegram remains the only remote action surface.

### R9 - V2 Release Stabilization (`PLANNED`, P0)

**Spec**: `specs/029-v2-release-stabilization`

- [x] Define terminal dependency states, runtime-payload identity and stable
  R001-R025 cross-feature matrix.
- [ ] Freeze an evidence-eligible candidate after Specs 021-028 reach terminal states.
- [ ] Run full cross-feature, core-safety, QA and auxiliary-outage regression.
- [ ] Complete release backup and staging restore.
- [ ] Controlled service activation and read-only smoke.
- [ ] One continuous 168-hour review with daily reports and an hour-72 checkpoint.
- [ ] Three documentation sweeps, secret hygiene and explicit release decision.

**Invariant**: no new feature during stabilization; any P0/P1 blocks release.

## Deferred Technology

- OpenTelemetry until multiple long-lived services, remote backends or tracing
  requirements justify an OTLP pipeline.
- MQTT until a selected physical device publishes trustworthy telemetry.
- Continuous Vnish WebSocket workers until bounded collection demonstrably
  misses time-critical evidence and reconnection semantics are proven.
- Remote/public web UI, web actions, React SPA and cloud deployment.
- Windows monitor containerization while Hashcore and service integration remain
  host-local.

## Completed Capability Baseline

- [x] Persistent SQLite history and reboot-decision audit.
- [x] Current finite-signal and persisted-startup safety.
- [x] Vnish board, temperature, fleet and firmware-transition interlocks.
- [x] Stability, quality, firmware and read-only diagnosis intelligence.
- [x] Bounded Vnish log collection with no-window scheduling.
- [x] Static operations dashboard.
- [x] Telegram no-silence delivery and click-safe actions.
- [x] Persistent/episode alerts and truthful current status in committed code.

## Governance

- `.specify/feature.json` stays on Spec 021 until its D+1/D+3 observation gate
  closes.
- Only one production-affecting spec may roll out at a time.
- Read-only discovery can overlap only when it does not touch the monitor.
- P0/P1 incidents interrupt the calendar; displaced dates move.
- Completion requires evidence, roadmap/calendar/docs synchronization and the
  post-release review defined for the spec.
