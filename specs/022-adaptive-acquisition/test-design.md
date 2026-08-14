# Test Design: Adaptive Acquisition Resilience

**Status**: Pre-D+1 red-contract design only. No test module, acquisition source
or runtime wiring is created before the Spec 021 D+1 implementation gate.

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

## Gate To Executable Tests

After real Spec 021 D+1 passes:

1. Add `tests/test_acquisition.py` with the groups above and observe the expected
   red failures because `app/acquisition.py` does not exist.
2. Implement only the pure model/config/normalizer needed to turn those tests
   green.
3. Add executor/lease tests before executor code.
4. Keep monitor wiring and defaults unchanged until sequential parity and the
   Spec 021 D+3 activation gate pass.

This file is design evidence, not a checked implementation task.
