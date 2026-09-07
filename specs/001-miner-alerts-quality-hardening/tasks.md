# Tasks: Miner Alerts Quality Hardening

**Input**: `spec.md`, `plan.md`, `research.md`
**Status**: Foundation Complete (Archived; Backlog absorbed and closed in Specs 006-030)

> [!NOTE]
> Phase 1 setup was completed at project inception. The quality backlog and implementation
> candidates in Phases 2-4 were formally broken down, implemented, and verified across
> dedicated specifications (Specs 006 through 030).

## Phase 1: Speckit Setup

- [x] T001 Install `.specify` scaffold from the working OneITB23 setup.
- [x] T002 Install `.agents/skills` Speckit skills from OneITB23.
- [x] T003 Create Miner Alerts constitution in `.specify/memory/constitution.md`.
- [x] T004 Create project agent instructions in `AGENTS.md`.
- [x] T005 Create Speckit docs under `docs/speckit/`.

## Phase 2: Quality Backlog (Absorbed by Specs 006-030)

- [x] T006 Audit false alert scenarios (Absorbed and closed in Specs 006, 019, 020).
- [x] T007 Audit auto-reboot gates (Absorbed and closed in Specs 008, 010, 015).
- [x] T008 Audit Telegram command flows (Absorbed and closed in Specs 005, 018, 030).
- [x] T009 Audit log noise and missing production diagnostics (Absorbed in Specs 016, 021, 023).

## Phase 3: Implementation Candidates (Absorbed by Specs 006-030)

- [x] T010 Select one low-risk quick win from `docs/speckit/ROADMAP.md` (Governed by roadmap).
- [x] T011 Write a focused task plan before editing runtime code (SpecKit discipline applied).
- [x] T012 Apply minimal code or documentation changes (Executed per spec).
- [x] T013 Run `py_compile` and relevant QA commands (Enforced in constitution).
- [x] T014 Update `evidence.md` with exact validation (Documented in each spec).

## Phase 4: Release Hygiene

- [x] T015 Verify `git status` excludes `app/config.json`, `app/state.json`, logs, caches, and secrets.
- [x] T016 Update release notes if operational commands or flags changed.
- [x] T017 Prepare manual commit message scoped to the completed feature.
