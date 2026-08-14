# Evidence: Operator Interface Decision

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 025 Grafana evaluation and Spec 028 backup/restore proof.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Existing Static Interface Baseline - 2026-08-13

- `tools/operations_dashboard.py` opens SQLite with URI `mode=ro`, uses bounded
  rows/windows, escapes persisted text and contains no monitor, network,
  subprocess or mutating SQL path.
- Against the local production SQLite database it generated an ignored
  self-contained 50,741-byte HTML artifact in 2,860 ms.
- `tests.test_operations_dashboard`: 5/5 PASS, including read-only enforcement,
  bounded view model, escaping, empty store and dependency-path audit.
- This baseline proves generator availability only. Visual/operator workflow
  completion remains unverified and Grafana/restore dependencies are incomplete;
  the decision remains `blocked`.

## Required Evidence Before Completion

- Completed workflow scorecard.
- Three timed runs per eligible P1 workflow/interface pair.
- Signed no-build or scoped-MVP decision.
- Conditional-file absence audit if no-build is selected.
- Conditional route/OpenAPI/no-action audit.
- Query latency and bounded-result evidence.
- Service isolation and D+1/D+3 notes if built.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
