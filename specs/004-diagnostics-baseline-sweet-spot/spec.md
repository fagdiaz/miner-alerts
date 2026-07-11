# Feature Specification: Diagnostics Baseline Sweet Spot

## User Story

As an operator, I want repeated diagnostics snapshots summarized into a
per-miner baseline, so that Miner Alerts can distinguish normal variance from
conditions that justify restart/reboot investigation.

## Scope

In scope:

- Read one or more `snapshot.json` files produced by `tools/miner_diagnostics.py`.
- Aggregate per-miner TH/s, board count, temperatures, Vnish voltage/frequency,
  consumption, and hardware error hints.
- Generate read-only `baseline.md` and `baseline.json` outputs.
- Work with a single snapshot, but mark confidence as low until multiple samples exist.

Out of scope:

- Changing auto-reboot policy.
- Writing `app/state.json`.
- Calling Hashcore Toolkit or miner action commands.
- Runtime dashboard.

## Acceptance Criteria

- The baseline tool compiles with Python.
- The baseline tool can process `diagnostics/latest/snapshot.json`.
- Outputs are written under an ignored diagnostics folder.
- Report includes sample count and confidence level per miner.
- Report keeps the data descriptive; it does not recommend automatic action changes.
