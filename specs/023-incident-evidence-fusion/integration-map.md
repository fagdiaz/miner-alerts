# Integration Map: Incident Evidence Fusion

## Purpose

Map Spec 023 onto the current persisted evidence and read-only operator paths
before implementation. This document fixes ownership boundaries so fusion
cannot become a second collector, state machine or action policy.

## Current Authoritative Path

The current production flow is:

```text
API 4028 tick
  -> state machine and action gates in app/miner_monitor.py
  -> telemetry_samples / operational_events / reboot_decisions

bounded Vnish collector
  -> firmware_events / collector_runs

Telegram /diagnose and static dashboard
  -> bounded EventStore reads
  -> existing stability, mining-quality and restart analyzers
```

Spec 023 is inserted only after persistence:

```text
persisted rows + explicit assessment window
  -> evidence normalization
  -> conservative versioned rules
  -> additive assessment persistence
  -> one shared read-only renderer
```

It does not run miner IO, collect Vnish logs, call Hashcore, update miner state,
or feed an assessment back into reboot eligibility.

## Existing Source Inventory

| Source | Current owner | Stable time | Identity | Eligible content |
| --- | --- | --- | --- | --- |
| `telemetry_samples` | `EventStore.record_sample` | `observed_ts` | table row `id` + `miner_key` | state, response, finite rate, threshold, boards, elapsed, thermal, power-domain board data, quality counters/flags |
| `operational_events` | `EventStore.record_event` | `occurred_ts` | table row `id` | state changes, restarts, episode/action summaries and structured details |
| `reboot_decisions` | `EventStore.record_reboot_decision` | `evaluated_ts` | table row `id` | exact allow/block result and guard evidence |
| `firmware_events` | bounded Vnish collector | `source_ts_epoch` when parsed; otherwise `collected_ts` | table row `id` + fingerprint | normalized firmware category, severity and code |
| `collector_runs` | bounded Vnish collector | `completed_ts` | table row `id` | collector availability, partial/failure and truncation evidence |
| Spec 022 envelope | adaptive acquisition | `observed_ts` + epoch identity | persisted sample reference | authority, quality and stable reason code |

Free-form summaries are display context only. They cannot create stable fact
codes, source identity or causal confirmation.

## Existing Reusable Analyzers

| Module | Reuse | Boundary |
| --- | --- | --- |
| `app/stability_profile.py` | Baseline eligibility, stable bands and deterministic health reasons | Fusion consumes returned values; it does not duplicate baseline math. |
| `app/mining_quality.py` | Normalization and share/error quality assessment | Quality reasons remain observations, not root causes. |
| `app/restart_intelligence.py` | Existing action attribution semantics | The configured attribution window remains authoritative. |
| `app/alert_episodes.py` | Episode identity and bounded state chronology | Fusion references episode events; it does not emit reminders. |
| `app/vnish_logs.py` | Stable firmware codes and source-clock quality | Unparsed source time cannot prove ordering. |

## Planned Source Scope

| File | Planned responsibility | Explicit non-responsibility |
| --- | --- | --- |
| `app/evidence_fusion.py` | Pure normalization, canonical digest, rules and renderer input | No SQLite connection, wall-clock lookup, network or action call |
| `app/event_store.py` | Bounded source queries, additive migration, assessment save/load | No confidence or cause decisions |
| `app/miner_monitor.py` | Feature flag, explicit `now_ts`, `/diagnose` adapter | No duplicate fusion rules; existing diagnosis remains fallback |
| `tools/operations_dashboard.py` | Render the same persisted/shared assessment | No independent cause scoring |
| `tests/test_evidence_fusion.py` | Replay matrix and safety invariants | No live miner dependency |
| `tests/test_event_store.py` | Migration, indexes, idempotency and bounded query tests | No production database fixture |

## Query Boundary

An assessment request supplies all of the following explicitly:

- `subject_type`: `incident`, `episode` or `miner_window`.
- `subject_ref`: stable incident/event ID, episode ID, or miner key plus window.
- `window_start_ts` and `window_end_ts`.
- `assessment_now_ts`, captured once by the caller.
- `ruleset_version` from code.

EventStore reads only rows inside that window plus the latest collector run at
or before `assessment_now_ts`. Every source query has a deterministic order and
hard limit. The first implementation targets at most ten miners and a 24-hour
context; it must not perform one query per telemetry row or firmware event.

## Deterministic Pipeline

1. Query bounded rows using indexed source time and miner identity.
2. Normalize only recognized fields into immutable `EvidenceFact` values.
3. Sort facts by `(effective_ts, source, source_row_id, code)`.
4. Canonically serialize facts with sorted keys and fixed numeric handling.
5. Calculate `evidence_digest` without database ID or generation wall time.
6. Evaluate the versioned rules in stable cause-code order.
7. Persist one assessment per subject, ruleset and evidence digest.
8. Render persisted facts, hypotheses, contradictions and missing evidence.

Repeated evaluation of the same source rows, explicit window and ruleset must
produce the same digest and semantic assessment.

## Integration Anchors

| Current anchor | Spec 023 integration |
| --- | --- |
| `build_miner_diagnosis_text` in `app/miner_monitor.py` | When disabled or unavailable, preserve the current output exactly. When enabled, call the shared assessment service with explicit time/window. |
| `/diagnose` branch in `telegram_polling_worker` | Keep command parsing, authorization, queue and no-silence behavior unchanged; replace only the detail text source behind the flag. |
| EventStore schema initialization | Add schema version and tables additively; old tables and readers remain valid. |
| Static dashboard incident detail | Use the same renderer result or persisted assessment; do not implement dashboard-specific scoring. |
| Existing action-policy block | No call from assessment output into `record_auto_reboot_decision`, `run_hashcore_cli` or state transitions. |

## Failure Behavior

| Failure | Required result |
| --- | --- |
| EventStore unavailable | Existing diagnosis fallback or explicit historical-diagnosis unavailable message |
| One source query fails | Assessment marked incomplete; missing source visible; no confidence promotion |
| Collector stale/failed | Firmware evidence marked missing or stale; miner health is not inferred |
| Source clock unparsed | Fact remains visible with uncertain clock and cannot prove order |
| Persistence fails | Render may use the computed read-only result, but it is labeled unpersisted and cannot claim replayability |
| Unknown fact/cause code | Preserve as unsupported input metadata or ignore safely; never promote confidence |
| Performance budget exceeded | Return bounded unavailable/incomplete result; never fall back to unbounded reads |

## Activation And Rollback

1. Implement and replay with `incident_fusion_enabled=false`.
2. Compare enhanced output against current `/diagnose` and raw event evidence.
3. Enable only the read-only Telegram/dashboard detail path after Spec 022
   quality evidence and Spec 023 contract tests pass.
4. Disable the flag to restore the existing diagnosis path immediately.
5. Additive assessment tables may remain; no rollback deletes source evidence.

Production activation cannot overlap another production-affecting rollout and
must complete its own D+1/D+3 review.
