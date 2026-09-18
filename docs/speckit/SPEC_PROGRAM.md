# Miner Alerts Specification Program

**Planning baseline**: 2026-09-15
**Program horizon**: 2026-09-15 to 2026-12-20
**Active production gate**: V5.0.3 Cold-Boot Fleet Grace Period Approved (`v5.0.3`, 1062 tests PASS, Windows Service RUNNING)
**Canonical schedule**: `docs/speckit/DELIVERY_PLAN.md`

## Purpose

This program converts the approved roadmap into implementation-ready Speckit
packages. It defines sequence, dependencies, safety class, technology gates and
the evidence required before each package may close. It is planning only: the
presence of a spec does not mean that its code, rollout or runtime behavior has
been completed.

## Current Baseline

- The Windows service remains the production runtime and `app/miner_monitor.py`
  remains the only monitor/action authority.
- API 4028 polling is the authoritative miner-health acquisition path.
- Vnish WebSocket collection is bounded, scheduled and read-only; it enriches
  evidence but does not replace API 4028 or authorize actions.
- SQLite schema v7 in WAL mode is the durable incident, sample, firmware and decision store.
- Telegram is the remote control surface; the static operations dashboard is
  read-only.
- Specs 001 through 066 are 100% completed, verified, and evidenced in production.
- Production runtime has operated continuously with a certified test suite of 1062 tests PASS (0 failures, 0 errors, 0 regressions).
- Production Windows service `MinerAlerts` is running continuously under Windows 11.

## Decisions Made In This Planning Pass

1. **Spec 020 closeout remains separate from Spec 021 liveness.** Spec 020 owns
   episode-alert rollout evidence; Spec 021 independently owns heartbeat,
   watchdog and SCM recovery evidence.
2. **API 4028 polling remains authoritative.** The deployed protocol is
   request/response. WebSockets are retained only where Vnish actually publishes
   asynchronous firmware evidence.
3. **Adaptive acquisition separates authoritative samples from diagnostic
   probes.** Faster temporary probes may improve visibility but must not advance
   state streaks, sustained-LOW timers or auto-reboot eligibility.
4. **Monitor liveness is supervised out of process.** The watchdog reads a
   bounded heartbeat and service state, can notify, and has no miner or Hashcore
   action path.
5. **Prometheus/Grafana are the preferred observability stack.** A local-only
   exporter reads durable/read-only state; it is not embedded as a second action
   surface in the monitor.
6. **Docker is limited to auxiliary observability services.** The Windows monitor
   and Hashcore integration stay native because they depend on Windows service,
   local paths and Toolkit execution.
7. **FastAPI is conditional.** Static HTML plus Grafana are evaluated first. A
   local-only read API/MVP is built only if a measured operator workflow remains
   unsolved; React is not a default dependency.
8. **Electrical telemetry begins with source discovery.** AC input voltage is
   never inferred from hashboard/chain voltage. SNMPv3, Modbus TCP, vendor HTTPS
   or MQTT are selected only after a real PDU/UPS/meter publisher is identified.
9. **Hashcore expansion starts with a read-only inventory.** Unknown commands are
   classified as mutating until proven otherwise. Existing reboot/restart scope
   does not expand in Spec 026.
10. **OpenTelemetry is deferred.** One Windows process, one auxiliary collector
    and local Prometheus metrics do not yet justify an OTLP collector pipeline.
11. **SQLite backup uses the SQLite backup interface, not a blind live file
    copy.** Restore is first rehearsed to a staging path and never overwrites the
    live database automatically.
12. **Every production-affecting spec has a separate observation/fix window.**
    Calendar pressure moves dates; it cannot remove runtime evidence gates.

## Program Inventory

| Order | Spec | Priority | Risk | Depends on | Outcome |
| --- | --- | --- | --- | --- | --- |
| Closed | 020 Episode Alerts closeout | P0 | HIGH | Current runtime | Completed and runtime-closed 2026-08-13. |
| Closed | 030 Telegram Messaging Quality | P0 | MEDIUM | Spec 020 runtime | Completed, activated and pushed 2026-08-13. |
| Closed | 021 Monitor Liveness Watchdog | P0 | HIGH | Spec 020 complete | Completed and closed 2026-08-20 (77.3h soak). |
| Closed | 022 Adaptive Acquisition | P1 | HIGH | 021 D+1 for wiring | Completed and closed 2026-08-27 (267h+ runtime proven). |
| Closed | 023 Incident Evidence Fusion | P1 | MEDIUM | 022 | Completed and closed 2026-08-28 (`/diagnose` active). |
| Closed | 024 Electrical Source Discovery | P1 | MEDIUM | 023; real hardware | Completed and closed 2026-08-28 (`blocked_external`). |
| Closed | 025 Prometheus Metrics | P1 | MEDIUM | 021, 022 | Completed and closed 2026-08-29 (Prometheus & Grafana active). |
| Closed | 026 Hashcore Capability Inventory | P2 | MEDIUM | 021; Toolkit present | Completed and closed 2026-08-29 (Metadata & allowlist inventory). |
| Closed | 028 Backup Retention Restore | P1 | HIGH | Stable schema after 023 | Completed and closed 2026-08-30 (Online backup & staging restore passed). |
| Closed | 027 Operator Interface Decision | P2 | MEDIUM | 025, 028 | Completed and closed 2026-08-30 (`no_build` decision). |
| Closed | 029 V2 Release Stabilization | P0 | HIGH | All accepted packages | Completed and approved 2026-09-07 (`v2.0.0` release). |

The directory numbers preserve the roadmap concepts created before this program.
Execution order is governed by dependencies and priority, so Spec 028 is
scheduled before conditional Spec 027.

### Horizon V5.0 Certified Packages (Specs 057–066)

| Order | Spec | Priority | Risk | Module Scope | Outcome |
| --- | --- | --- | --- | --- | --- |
| Closed | 057 Intervention Governance | P1 | MEDIUM | `app/governance/`, Telegram | Completed, Vnish Free Mode & Adaptive Contingency (`v4.1.5`, 902 tests PASS). |
| Closed | 058 Telegram Dispatcher | P1 | LOW | `app/telegram/router.py` | Completed, MT-01 Modular Router & Dispatcher (`v5.0.0`, 910 tests PASS). |
| Closed | 059 Hardware Clients Extraction | P1 | MEDIUM | `app/network/` | Completed, MT-02 CGMiner, Vnish & Hashcore Clients (`v5.0.0`, 928 tests PASS). |
| Closed | 060 Core Daemon Architecture | P0 | HIGH | `app/core/` | Completed, ST-01/ST-02 MonitorContext & StateManager L1/L2 (`v5.0.0`, 958 tests PASS). |
| Closed | 061 SQLite WAL Integrity | P1 | LOW | `app/core/event_store.py` | Completed, PROP-002 WAL Mode & Quick Check (`v5.0.1`, 969 tests PASS). |
| Closed | 062 HW Error Tripwire | P2 | MEDIUM | `app/governance/preset_balancer.py` | Completed, PROP-003 HW Error Tripwire & 48h Lock (`v5.0.1`, 979 tests PASS). |
| Closed | 063 Ambient Thermal PID | P2 | MEDIUM | `app/governance/fan_governor.py` | Completed, PROP-004 Seasonal Thermal PID & Inlet Guards (`v5.0.1`, 993 tests PASS). |
| Closed | 064 Multi-Miner Charts | P3 | LOW | `app/telegram/charts.py` | Completed, PROP-006 Multi-Miner Charts & Range Switchers (`v5.0.2`, 1004 tests PASS). |
| Closed | 065 Supervisory Hooks | P1 | MEDIUM | `app/core/engine.py` | Completed, ST-04 Declarative 7-Stage Hooks Pipeline (`v5.0.2`, 1047 tests PASS). |
| Closed | 066 Cold-Boot Fleet Grace | P1 | LOW | `app/miner_monitor.py` | Completed, PROP-001 Cold-Boot 180s Fleet Warmup Grace (`v5.0.3`, 1062 tests PASS). |

### Horizon V5.1 Packages (Specs 067–073)

| Order | Spec | Priority | Risk | Depends on | Outcome / Objective |
| --- | --- | --- | --- | --- | --- |
| Closed | 067 Gateway Heartbeat & Storm Suppression | P2 | LOW | Spec 066 | Worker TCP 50ms hacia router y supresión de tormentas 15s (PROP-005, 1072 tests PASS). |
| Closed | 071 SQLite Pool & Daemon Thread Hardening | P1 | LOW | Spec 067 | Pool multi-lector resiliente y barreras try/except en hilos daemon (1079 tests PASS). |
| Audited (Planned) | 072 State Serialization Unification | P2 | LOW | Spec 071 | Unificación DRY de serialización de MinerState y helpers seguros (Planificado/Auditado). |
| Audited (Planned) | 073 Tools Client Reuse & Config Alignment | P3 | LOW | Spec 072 | Reutilización de cgminer_client en tools y validador de config (Planificado/Auditado). |
| Audited (Planned) | 070 Core Modularization Phase B (Harness) | P0 | HIGH | Spec 073 | Sustitución de inspect.getsource(main) por Behavioral Test Harness (Planificado/Auditado). |
| Audited (Planned) | 068 IPC Watchdog Named Pipe | P3 | MEDIUM | Spec 070 | Servidor Named Pipe con SDDL y wake-up unblock <15s (Planificado/Auditado). |
| Audited (Planned) | 069 Deep Chain Telemetry & Predictive Break | P1 | MEDIUM | Spec 070 | Telemetría profunda por cadena, persistencia I2C >=24 muestras (Planificado/Auditado). |

## Implementation Readiness And Hard Gates

All implemented packages (Specs 001 through 067, and Spec 071) have satisfied their planning, implementation,
validation, and production soak gates. The system is stabilized and certified
under Release v5.1.0 (1110 tests PASS).

Specs 068, 069, 070, 072, and 073 are fully specified and audited by QA with all edge-case mitigations,
and remain paused awaiting explicit implementation trigger.

Documentation and sanitized fixtures may advance in parallel. Runtime code,
activation or a new long-lived component cannot bypass the hard blocks above.

## Cross-Spec Risk Register

| Risk | Containment contract | Closing evidence |
| --- | --- | --- |
| Adaptive acquisition changes state/action timing | One ordered authoritative envelope per miner/epoch; diagnostic probes have no authority | Sequential parity, bounded request counts, action/offset invariants, D+1/D+3 |
| Correlation presents an unsupported root cause | Direct-evidence ceilings, visible contradictions/missing sources, timing-only suspected at most | Deterministic replay and confidence-wording audit |
| Miner board voltage is mistaken for AC input | Spec 024 external-source-only electrical contract | Proven PDU/UPS/meter adapter or explicit blocked outcome |
| Metrics/exporter becomes a second authority | Atomic sanitized read-only snapshot; no monitor action imports | Outage isolation, redaction/cardinality and dependency audit |
| Hashcore discovery executes an unknown mutation | Metadata-only default; exact fingerprint-bound vendor allowlist; unknown classified mutating | Zero-process rejection, sanitized inventory, timeout/no-window and unchanged action-scope proof |
| Backup corrupts or overwrites live history | SQLite online backup, atomic promotion, staging-only restore | Concurrent-write integrity, manifest/hash and staging restore drill |
| Optional UI expands attack/action surface | No-build first; loopback, SQLite read-only and no action/config routes if built | Workflow scorecard, route/import audit and monitor outage isolation |
| Calendar pressure compresses safety gates | Gates move dates and code changes reset affected observation | Evidence timestamps and explicit approve/block decision |

## Dependency Graph

```mermaid
flowchart TD
    S020["Spec 020: complete"] --> S021["Spec 021: active observation gate"]
    S020 --> S030["Spec 030: messaging quality complete"]
    S021 --> S022["Spec 022: adaptive acquisition"]
    S022 --> S023["Spec 023: evidence fusion"]
    S023 --> S024["Spec 024: electrical discovery"]
    S021 --> S025["Spec 025: Prometheus metrics"]
    S022 --> S025
    S021 --> S026["Spec 026: Hashcore inventory"]
    S023 --> S028["Spec 028: backup and restore"]
    S025 --> S027["Spec 027: interface decision"]
    S028 --> S027
    S024 --> S029["Spec 029: v2 stabilization"]
    S025 --> S029
    S026 --> S029
    S027 --> S029
    S028 --> S029
```

## Shared Architecture Boundaries

### Action Authority

- Only the existing monitor may call Hashcore reboot/restart paths.
- Watchdog, exporter, dashboard, backup tooling and discovery probes are
  read-only with respect to miners.
- No new web, metrics, MQTT, SNMP or electrical signal may authorize automatic
  action in this program.

### Source Of Truth

- Current miner signal: authoritative API 4028 sample.
- Confirmed state/action eligibility: existing state machine and safety gates.
- Firmware context: bounded Vnish collector evidence.
- Historical incidents/decisions: SQLite.
- Monitor liveness: independent heartbeat plus process/service observation.
- Electrical facts: selected external device with source timestamp and quality.

### Runtime Topology

```text
Windows native
|-- MinerAlerts service: polling, state machine, Telegram, action authority
|-- Vnish collector task: bounded read-only firmware evidence
|-- Monitor watchdog task: heartbeat/service checks and liveness notification
|-- Backup task: SQLite online backup and manifest
`-- Metrics exporter: localhost read-only endpoint

Optional Docker
|-- Prometheus
`-- Grafana
```

## Shared Validation Gates

Every spec must apply the gates relevant to its risk class.

| Gate | LOW | MEDIUM | HIGH |
| --- | --- | --- | --- |
| Requirements checklist and cross-artifact analysis | Required | Required | Required |
| Targeted unit/contract tests | If executable behavior changes | Required | Required, test-first |
| Full Python regression and `py_compile` | If Python changes | Required | Required |
| QA no-action proof | Not applicable | If command/diagnostic path touches action context | Required |
| Controlled Windows service activation | No | If long-lived service changes | Required |
| D+1/D+3 runtime review | No | Required for long-lived components | Required |
| Rollback/restore evidence | Documented | Required where persisted/runtime state changes | Required |
| Core invariant comparison | No | Scoped | State machine, polling offset and auto-reboot required |

## Spec Definition Of Done

A future spec is complete only when all of the following are true:

1. `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`,
   `quickstart.md`, `tasks.md`, `checklists/requirements.md` and `evidence.md`
   agree on names, scope and validation.
2. Every task is checked only after its evidence is recorded.
3. Unverified production behavior is marked pending or blocked.
4. Real config, state, database copies, logs, credentials and miner addresses are
   absent from Git.
5. `ROADMAP.md`, `DELIVERY_PLAN.md`, strategy docs and the newest-first
   development log are synchronized in the same closeout.
6. Production-affecting work completed its observation/fix window with no open
   P0/P1 regression.

## Documentation Sweep Protocol

The program requires three documentation sweeps.

### Sweep 1 - After Spec Generation

- Validate all 021-029 artifact sets and requirement/task coverage.
- Resolve naming, dependency, risk and technology conflicts.
- Recalculate dates from the real current date, never from an expired estimate.

### Sweep 2 - Cross-Spec Consistency

- Compare contracts for heartbeat, acquisition quality, incidents, metrics,
  power samples, backups and interface reads.
- Confirm no secondary service gains action authority.
- Confirm Telegram, static HTML, Grafana and optional FastAPI use consistent
  operator terms and freshness semantics.

### Sweep 3 - Final Governance

- Synchronize this program, roadmap, delivery calendar, strategy docs, runbook,
  README and constitution references.
- Verify links, statuses, dates, local-only boundaries and secret hygiene.
- Record why any spec was added, split, reordered or deferred.

## Changes To The Earlier Roadmap

- Dates from the 2026-07-22 draft were expired and are recalculated from
  2026-08-13.
- Spec 020 closeout remains its own task rather than being renamed as Spec 021.
- Backup/retention/restore is promoted into dedicated Spec 028 instead of being
  hidden inside the final stabilization window.
- Final cross-feature release work is made explicit as Spec 029.
- Interface work remains conditional and moves after backup proof.
- OpenTelemetry, continuous Vnish WebSockets, MQTT without a publisher and web
  action controls remain deferred because their prerequisites are not present.

## Planning Audit Record - 2026-08-13

### Sweep 1 - Artifact Quality

- The original sweep validated 81 artifacts across nine packages. After Spec
  021 implementation evidence and Specs 022-029 hardening, the current 021-029
  baseline contains 101 artifacts, 27 user stories, 128 functional
  requirements, 61 measurable success criteria and 146 ordered tasks.
- Confirmed every package has research, data model, contract, quickstart,
  requirements checklist, rollback boundary and initial evidence record.
- Found and corrected one cross-template omission: risk classification was
  explicit in specs/tasks but not in plans.
- No unresolved clarification, TODO or TBD marker remains in the planned
  artifacts.

### Sweep 2 - Cross-Spec Consistency

- Verified dependency references, program order and roadmap/calendar date
  ranges for Specs 020-029.
- Confirmed API 4028 authority, diagnostic-only Vnish/electrical evidence,
  one monitor action authority and conditional interface boundaries across all
  contracts.
- Clarified Spec 021 as `READY / GATED`, marked every future quickstart as a
  planned procedure, and made Spec 029 dependencies explicit.
- Preserved the deliberate Spec 028-before-027 execution order and the
  no-build outcome for optional interface work.

### Sweep 3 - Governance And Hygiene

- Verified local Markdown links, active-feature pointer, canonical dates,
  planned/implemented status language and absence of real tokens or private
  miner addresses in new planning artifacts.
- Synchronized roadmap, delivery calendar, strategy documents, README,
  Speckit guide, agent instructions and constitution references.
- Confirmed this pass changes documentation/specification artifacts only; it
  does not change runtime code, local config/state, Git history or the running
  Windows service.

### Open External Gates

- Spec 021 D+1/D+3 observation is the immediate production gate. Spec 022
  implementation waits for D+1 and activation waits for D+3.
- Spec 024 requires actual PDU/UPS/meter identity and documented read access.
- Spec 025 requires Docker availability or an approved native validation path.
- Spec 026 requires the installed Toolkit and proven safe discovery commands.
- Windows service/watchdog rollout requires an elevated maintenance window.

## Program State

- Specs 001 through 030 are **Completed, Tagged and Evidenced in Production** (`v2.0.0`).
- Specs 031 through 038 are **Completed, Hardened and Certified in Production** (`v3.0.0`).
- Specs 039 and 040 are **Completed, Calibrated for 83°C–84°C Operation, and Active in Production** (`v3.2.0`).
- Specs 041 and 042 are **Completed, Pure Modular Subpackages & Zero-Shim Cleanliness** (587 tests PASS).
- Specs 043 and 044 are **Completed, Interactive Command Center, Visitor Silent Mode & Safety Thermal Guard, and Active in Production** (`v3.3.0`, 621 tests PASS; Recalibrated 2026-09-12 for 30%–50% PWM, 82.0°C and independent elevators).
- Specs 045 through 047 are **Completed, Mobile-First Visual Navigation, Categorical Help & Compact Cards <= 32 cols** (`v3.5.0`, 721 tests PASS).
- Specs 048 through 052 are **Completed, Safe Fleet Shutdown, Active Purge Ramp, Post-Blackout Guard, Fast Phase Drop Discriminator & Maintenance Scheduler** (`v3.7.0`, 781 tests PASS).
- Spec 053 is **Completed, Governance Concurrency Hardening, Reentrant Mutexes & V4 Release Candidate Certified** (`v4.0.0`, 792/792 tests PASS).
- Release Hotfix V4.0.1 is **Completed, Post-Blackout Persistence Hardening & Concurrency Scope Hotfix Verified in Live Production** (`v4.0.1`, 797/797 tests PASS).
- Release V4.0.2 / Spec 044 Recalibration is **Completed, Silent Mode 30%–50% PWM, 82.0°C Regulation & Independent Elevator Modulation Verified in Live Production** (`v4.0.2`, 800/800 tests PASS).
- Release V4.0.3 / Fan Floor 30% Hotfix is **Completed, Minimum Fan Duty Floor Calibrated to 30% for Full Thermal Modulation Bandwidth Down to 82.0°C Target** (`v4.0.3`, 802/802 tests PASS).
- Spec 054 is **Completed, Deep Chain Telemetry Ingestion, SQLite v7 Storage, Predictive Hashboard Diagnostics & Interactive /chains UX Certified in Live Production** (`v4.1.0`, 835/835 tests PASS).
- Spec 055 is **Completed, Automated Hashboard Failure Recovery, 6-Interlock Auto-Reboot & Sustained 600s Window Certified in Live Production** (`v4.1.3`, 854/854 tests PASS).
- Spec 056 is **Completed, Two-Tier Mining Recovery (Soft Auto-Restart via Vnish REST vs Hard Auto-Reboot via Hashcore CLI) Certified in Live Production** (`v4.1.4`, 881/881 tests PASS).
- Spec 057 is **Completed, Intervention Governance & Adaptive Contingency Certified in Live Production** (`v4.1.5`, 902/902 tests PASS).
- Specs 058 through 060 are **Completed, Telegram Command Center & Dispatcher Modularization, Hardware Clients Extraction & Core Daemon Architecture Certified** (`v5.0.0`, 958/958 tests PASS).
- Specs 061 through 063 are **Completed, SQLite WAL Mode Integrity, HW Error Tripwire & Ambient-Aware Seasonal Thermal PID Certified** (`v5.0.1`, 993/993 tests PASS).
- Specs 064 and 065 are **Completed, Multi-Miner Charts & Range Switchers, Declarative Hooks Pipeline in CoreSupervisoryEngine Certified** (`v5.0.2`, 1047/1047 tests PASS).
- Spec 066 is **Completed, Cold-Boot Fleet Grace Period Post-Arranque (PROP-001) Certified in Live Production** (`v5.0.3`, 1062/1062 tests PASS).
- Spec 074 is **Completed, Paired Elevator Contingency & Inrush Dampening (PROP-009) Certified in Live Production** (1221/1221 tests PASS).
- Spec 075 is **Completed, Soft-Landing Recovery, Headroom Chilling & APW12 Latch-Off Defense (PROP-010) Certified** (1236/1236 tests PASS).
- All 75 specifications across the program have satisfied their design, test, concurrency, and evidence gates with 1236/1236 passing automated tests.

## Planning Hardening Record - 2026-08-13

- Corrected the active gate, baseline, inventory and feature-pointer record to
  reflect completed Specs 020/030 and active Spec 021 observation.
- Hardened Spec 022 around the exact sequential acquisition seam, stable quality
  codes, bounded workers/deadlines/leases and disabled-by-default config.
- Hardened Spec 023 around existing EventStore sources, explicit clock/freshness
  rules, canonical replay, conservative confidence, bounded queries and shared
  read-only rendering.
- Hardened Spec 025 around one atomic sanitized snapshot, an exact metric
  allowlist/cardinality formula, stale health-only behavior and prohibited
  container mounts.
- Hardened Spec 028 around SQLite API-only backup, marked disjoint roots,
  atomic verification, UTC union retention and staging-only restore proof.
- Hardened Spec 024 around the proven non-AC meaning of current miner fields,
  explicit blocked discovery, protocol read allowlists and bounded collection.
- Hardened Spec 026 around a statically proven Toolkit `1.6.0+167` installation,
  a pass-through wrapper, zero-process metadata-only default, empty reviewed
  allowlist, exact fingerprint binding and bounded/sanitized invocation rules.
- Hardened Spec 027 around fixed P1 workflows and three-run targets, dependency
  blocking, deterministic no-build, exact loopback GET/HEAD/query boundaries and
  explicit absence of conditional runtime files when no-build wins.
- Hardened Spec 029 around terminal dependency states, deterministic runtime
  payload identity, stable R001-R025 evidence, exact P0/P1 semantics, safe
  rollback and one continuous seven-day review with an hour-72 checkpoint.
- No future-spec planning change activated code, changed local runtime config or
  restarted the production service.
