# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include the validation needed to prove the acceptance scenarios. `py_compile`
alone is insufficient for Telegram delivery, Hashcore actions, polling behavior, or auto-reboot safety.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- Paths shown below assume single project - adjust based on plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Identify affected monitor, Telegram, config, or documentation paths
- [ ] T005 [P] Define validation commands and expected logs
- [ ] T006 [P] Confirm QA/production safety gates for this change

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 1

- [ ] T007 [P] [US1] Update the scoped file(s) identified in plan.md
- [ ] T010 [US1] Record command/log evidence in this spec

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T011 [P] Documentation updates in docs/
- [ ] T012 Code cleanup and refactoring
- [ ] T013 Run quickstart.md validation
- [ ] T014 Run the applicable Windows/Python validation commands
- [ ] T015 Execute the affected Telegram, Hashcore, polling, or QA flow end to end when relevant
- [ ] T016 Record the executed validation evidence in this feature
- [ ] T017 Recalculate `docs/project_docs/ROADMAP.md` from its checklists
- [ ] T018 Insert one feature entry at the top of `docs/audit/DEVELOPMENT_LOG.md`
- [ ] T019 Verify `DEVELOPMENT_LOG.md` is ordered newest to oldest
- [ ] T020 Update `docs/audit/DOCUMENTATION_STATUS.md` when status or canonical docs changed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

## Definition Of Done

- [ ] All required tasks are marked `[X]`
- [ ] Acceptance scenarios were validated with recorded evidence
- [ ] Backend and frontend builds pass when affected
- [ ] Telegram command names, config keys, and log strings match when affected
- [ ] Persistence survives reload when the feature stores data
- [ ] `ROADMAP.md` reflects checklist evidence
- [ ] `DEVELOPMENT_LOG.md` contains exactly one new feature entry at the top
- [ ] Every log entry is ordered newest to oldest
- [ ] Unverified or blocked behavior is not reported as complete
