# Test Design: Adaptive Acquisition Resilience

**Status**: T002-T005 implemented after the owner-approved 19 h 40 min healthy
observation. Monitor wiring remains blocked until Spec 021 D+1.

## Fixture Contract

`fixtures/acquisition-contract.json` is sanitized, deterministic and contains no
network endpoint. Future tests replace socket IO with a scripted adapter and use
an injected monotonic/wall clock. Sleeping, real threads and real miners are not
required to validate normalization, budgets, ordering or missed-epoch behavior.

## Planned Test Groups

### Configuration And Disabled Path

- absent and explicit `adaptive_acquisition_enabled=false` create no executor or
  lease and select the current sequential path;
- invalid types/ranges use the exact defaults from `contracts/config.md` and
  produce one sanitized warning per key;
- diagnostics cannot enable while acquisition is disabled;
- no environment variable overrides acquisition settings.

### Envelope Normalization

Table-drive every stable `(quality, reason_code)` pair from
`integration-map.md`, including empty payload, invalid JSON, missing summary,
non-finite rate, missing stats, timeout, transport error, late and overlap.
Assert all envelopes carry source, authority, epoch, observation/completion time,
latency and request counters. Raw exception text and endpoint data are absent.

### Epoch Completeness And Ordering

- completion order differs from configured order but returned envelopes remain
  in configured order;
- each configured miner has exactly one envelope, including timeout/overlap;
- duplicate and unknown result keys are rejected rather than applied;
- a worker completion after deadline remains attached to its original epoch and
  never crosses the authoritative boundary;
- host resume creates one new epoch ID and no catch-up work.

### Concurrency And Lease Safety

Use synchronization events rather than time sleeps:

- two-worker maximum is never exceeded;
- one slow miner does not block already runnable peers beyond SC-001;
- a lease persists through a late worker and blocks the next scheduled request;
- authoritative and diagnostic scheduler requests cannot overlap per miner;
- no automatic retry occurs after timeout/error.

### Request Budgets

- valid summary may issue exactly one conditional stats request;
- failed/invalid summary issues no stats request;
- one authoritative epoch consumes at most one summary plus one stats per miner;
- one diagnostic interval consumes at most one summary per eligible miner;
- manual command reads are not counted and never become envelopes.

### Authority Firewall

Feed diagnostic envelopes through a spy boundary and prove zero calls to state,
streak, `low_since_ts`, episode, persistence and action evaluators. Feed ordered
authoritative envelopes through the same boundary and compare the legacy fixture
sequence. Tick-level evaluation time remains one fixed value regardless of IO
completion times.

### Cross-System Invariants

- AST/source checks prove Telegram polling/offset code is untouched;
- action-policy tests prove startup, valid-signal, sustained LOW, firmware,
  fleet, temperature, cooldown, window and QA gates retain precedence;
- disabled deterministic replay matches legacy ordered state/action inputs;
- importing/testing `app.acquisition` performs no network, subprocess, service,
  file write or Hashcore operation.

## Executed Gate

On 2026-08-14 the following isolated steps were authorized and executed:

1. `tests/test_acquisition.py` failed red because `app.acquisition` was absent.
2. Pure model, config, transport, normalizer, scheduler, lease, executor and
   PollHealth contracts were implemented in `app/acquisition.py`.
3. Transport and legacy-board compatibility tests were added red before their
   corresponding implementation changes.
4. Monitor wiring, shared defaults and production runtime remain unchanged;
   D+1 still gates wiring and D+3 gates activation.

The remaining groups are completed only when their corresponding tasks close.
