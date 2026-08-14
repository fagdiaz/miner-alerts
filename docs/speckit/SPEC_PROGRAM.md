# Miner Alerts Specification Program

**Planning baseline**: 2026-08-13
**Program horizon**: 2026-08-13 to 2026-12-20
**Active production gate**: `specs/021-monitor-liveness-watchdog` (D+1/D+3 observation)
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
- SQLite schema v5 is the durable incident, sample, firmware and decision store.
- Telegram is the remote control surface; the static operations dashboard is
  read-only.
- Spec 020 is implemented, activated and runtime-closed. Spec 030 Telegram
  messaging quality is also implemented, activated and closed. Spec 021 is the
  current active gate: implementation, activation and controlled SCM recovery
  proof passed; D+1/D+3 observation remains open. Spec 022 implementation waits
  for Spec 021 D+1 and its production activation waits for Spec 021 D+3.

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
| Active | 021 Monitor Liveness Watchdog | P0 | HIGH | Spec 020 complete | Activated and SCM recovery-proven; D+1/D+3 pending. |
| 2 | 022 Adaptive Acquisition | P1 | HIGH | 021 | Improve freshness and poll evidence without changing action semantics. |
| 3 | 023 Incident Evidence Fusion | P1 | MEDIUM | 022 | Correlate durable miner, Vnish, quality and fleet evidence conservatively. |
| 4 | 024 Electrical Source Discovery | P1 | MEDIUM | 023; real hardware | Prove or block a trustworthy AC power telemetry source. |
| 5 | 025 Prometheus Metrics | P1 | MEDIUM | 021, 022 | Export bounded local metrics and provision Grafana read-only views. |
| 6 | 026 Hashcore Capability Inventory | P2 | MEDIUM | 021; Toolkit present | Produce a sanitized command/risk map without new actions. |
| 7 | 028 Backup Retention Restore | P1 | HIGH | Stable schema after 023 | Create verified SQLite backups and a staging restore drill. |
| 8 | 027 Operator Interface Decision | P2 | MEDIUM | 025, 028 | Decide whether Grafana/static HTML suffice; conditional local FastAPI MVP. |
| 9 | 029 V2 Release Stabilization | P0 | HIGH | All accepted packages | Cross-feature regression, restore proof, docs audit and release candidate. |

The directory numbers preserve the roadmap concepts created before this program.
Execution order is governed by dependencies and priority, so Spec 028 is
scheduled before conditional Spec 027.

## Implementation Readiness And Hard Gates

| Package | Planning readiness | May proceed now | Hard block before implementation/activation |
| --- | --- | --- | --- |
| 021 Liveness | Implemented and activated | D+1/D+3 read-only observation only | Close requires real scheduled D+1/D+3 evidence |
| 022 Acquisition | Implementation-ready plan | Red-contract preparation after 021 D+1 | Implementation waits for 021 D+1; activation waits for 021 D+3 |
| 023 Evidence fusion | Implementation-ready plan | Fixture curation and contract review | Code waits for Spec 022 authority/quality persistence and exit evidence |
| 024 Electrical | Discovery-ready, conditional | Physical inventory and documented read-only capability discovery | Adapter waits for a real source, authentication and no-write proof |
| 025 Metrics | Contract-ready | Metric-name/cardinality review | Snapshot implementation waits for 021/022 stable schemas |
| 026 Hashcore inventory | Metadata/contract ready | Vendor documentation review and static fingerprint refresh only | Local `1.6.0+167` identity is statically proven; invocation waits for an exact fingerprint-bound help/version allowlist |
| 028 Backup/restore | Contract-ready | Destination/path policy review | Implementation waits for stable post-023 schema and approved off-repo destination |
| 027 Interface | Fixed scorecard/conditional contract ready | Existing static generator baseline only | Three-run scorecard waits for 025/028; MVP files/dependencies exist only for exact P1 fields failed by all current owners |
| 029 Stabilization | Final-gate ready | Regression-matrix maintenance only | Candidate freeze waits for accepted/closed 021-028 outcomes |

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
  021 implementation evidence and Spec 022/023 hardening, the current 021-029
  baseline contains 92 artifacts, 27 user stories, 106 functional
  requirements, 50 measurable success criteria and 135 ordered tasks.
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

- Spec 021 is **Activated / Observation Pending**. Specs 022-029 are planned;
  Specs 020 and 030 are complete.
- `.specify/feature.json` points to Spec 021 until its D+1/D+3 evidence and
  closeout tasks complete.
- This multi-spec planning pass does not execute the Speckit Git feature hook:
  creating nine branches would misrepresent planned work as active work and the
  user explicitly excluded Git operations from this task.

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
- No future-spec planning change activated code, changed local runtime config or
  restarted the production service.
