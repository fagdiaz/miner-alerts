# Tasks: Miner Diagnostics And Interface Roadmap

## Phase 1: Documentation

- [x] T001 Expand `docs/speckit/ROADMAP.md` with diagnostics, Vnish, Hashcore, power telemetry, and interface phases.
- [x] T002 Create `docs/speckit/INTERFACE_STRATEGY.md`.
- [x] T003 Create `docs/speckit/MINER_DIAGNOSTICS.md`.
- [x] T004 Create `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`.

## Phase 2: Future Evidence

- [ ] T005 Collect sanitized Vnish log samples.
- [ ] T006 Inventory local Hashcore Toolkit commands and outputs.
- [ ] T007 Inspect actual API 4028 `stats` fields from S19j Pro miners.
- [ ] T008 Determine whether PSU/input voltage is exposed by firmware or requires external telemetry.

## Phase 3: Future Implementation Candidates

- [ ] T009 Add read-only diagnostics snapshot export.
- [ ] T010 Add Vnish event parser from sanitized samples.
- [ ] T011 Add Hashcore read-only capability inventory command.
- [ ] T012 Prototype local read-only report/dashboard.
