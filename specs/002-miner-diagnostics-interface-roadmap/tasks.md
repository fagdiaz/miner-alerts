# Tasks: Miner Diagnostics And Interface Roadmap

**Status**: Strategy Complete (Archived; Future evidence and implementations executed across Specs 003-030)

> [!NOTE]
> Phase 1 strategic roadmap was completed at project inception. The future evidence collection
> and implementation candidates outlined in Phases 2-3 were formally scoped, executed, and verified
> in dedicated specifications (Specs 003, 004, 009, 011, 013, 016, 024, 026, 027).

## Phase 1: Documentation

- [x] T001 Expand `docs/speckit/ROADMAP.md` with diagnostics, Vnish, Hashcore, power telemetry, and interface phases.
- [x] T002 Create `docs/speckit/INTERFACE_STRATEGY.md`.
- [x] T003 Create `docs/speckit/MINER_DIAGNOSTICS.md`.
- [x] T004 Create `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`.

## Phase 2: Future Evidence (Executed across Specs 003-026)

- [x] T005 Collect sanitized Vnish log samples (Executed in Spec 016).
- [x] T006 Inventory local Hashcore Toolkit commands and outputs (Executed in Spec 026).
- [x] T007 Inspect actual API 4028 `stats` fields from S19j Pro miners (Executed in Spec 003, 009).
- [x] T008 Determine whether PSU/input voltage requires external telemetry (Executed in Spec 024).

## Phase 3: Future Implementation Candidates (Executed across Specs 003-027)

- [x] T009 Add read-only diagnostics snapshot export (Executed in Spec 003).
- [x] T010 Add Vnish event parser from sanitized samples (Executed in Spec 016).
- [x] T011 Add Hashcore read-only capability inventory command (Executed in Spec 026).
- [x] T012 Prototype local read-only report/dashboard (Executed in Spec 011, 025, 027).
