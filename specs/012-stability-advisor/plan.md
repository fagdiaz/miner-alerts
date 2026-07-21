# Implementation Plan: Stability Advisor

## Technical Context

- Python standard library only: dataclasses, statistics, math, mappings.
- Existing SQLite schema-v2 telemetry through `EventStore.list_samples`.
- Existing Telegram polling dispatcher and command queue semantics.
- Existing static HTML operations dashboard and optional Docker generator.
- Windows service remains running on the previously loaded build.

## Constitution Check

- Production safety: PASS; analysis is read-only and cannot reach actions.
- Configuration source: PASS; only example defaults and bounded reads are used.
- Telegram controls: PASS; `/health` is read-only and replies deterministically.
- Auto-reboot gates: PASS; state machine and policy branches are out of scope.
- Windows compatibility: PASS; validation uses the repository virtualenv.
- Evidence completion: REQUIRED before commit.

## Design

1. Add a pure `app/stability_profile.py` analyzer.
2. Sort samples newest first, select the latest sample, and exclude it from baseline.
3. Build robust metric bands from prior healthy finite rows using median and MAD.
4. Apply hard current-signal reasons before advisory drift reasons.
5. Render bounded assessments for Telegram and expose structured dictionaries to the dashboard.
6. Add `/health [all|miner]` without live miner IO or action paths.
7. Extend the dashboard cards and summary using the same pure analyzer.
8. Keep Docker optional and copy only the analyzer needed by the generator.

## Safety Boundaries

- No auto-reboot, state machine, cooldown, startup guard, or Hashcore changes.
- No network call from the analyzer or `/health` branch.
- No persistence schema change and no new write path.
- Missing history degrades to `learning`; it never invents a stable result.
- AC input voltage is never inferred from chain voltage.

## Validation Strategy

- TDD for robust bands and all status outcomes.
- Static source assertion that `/health` contains no live-read or action call.
- Dashboard fixture assertions for shared status/reason rendering.
- Full unittest suite and py_compile for affected modules.
- Docker build/generation smoke.
- Speckit QA and service-status evidence without restart.
