# Tasks: Miner Alerts Quality Hardening

**Input**: `spec.md`, `plan.md`, `research.md`

## Phase 1: Speckit Setup

- [x] T001 Install `.specify` scaffold from the working OneITB23 setup.
- [x] T002 Install `.agents/skills` Speckit skills from OneITB23.
- [x] T003 Create Miner Alerts constitution in `.specify/memory/constitution.md`.
- [x] T004 Create project agent instructions in `AGENTS.md`.
- [x] T005 Create Speckit docs under `docs/speckit/`.

## Phase 2: Quality Backlog

- [ ] T006 Audit false alert scenarios and record findings in `evidence.md`.
- [ ] T007 Audit auto-reboot gates and record findings in `evidence.md`.
- [ ] T008 Audit Telegram command flows and record findings in `evidence.md`.
- [ ] T009 Audit log noise and missing production diagnostics.

## Phase 3: Implementation Candidates

- [ ] T010 Select one low-risk quick win from `docs/speckit/ROADMAP.md`.
- [ ] T011 Write a focused task plan before editing runtime code.
- [ ] T012 Apply minimal code or documentation changes.
- [ ] T013 Run `py_compile` and relevant QA commands.
- [ ] T014 Update `evidence.md` with exact validation.

## Phase 4: Release Hygiene

- [ ] T015 Verify `git status` excludes `app/config.json`, `app/state.json`, logs, caches, and secrets.
- [ ] T016 Update release notes if operational commands or flags changed.
- [ ] T017 Prepare manual commit message scoped to the completed feature.
