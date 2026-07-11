# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

**Language/Version**: [e.g., Python 3.11, React 18, .NET 6 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., requests, Telegram Bot API, Hashcore Toolkit CLI or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., JSON config/state files or N/A]

**Testing**: [e.g., pytest, XCTest, Jest or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Windows PowerShell, local miner network or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., command reply latency, polling stability or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., no unnecessary reboot, no secrets, QA guardrails or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/
```

**Structure Decision**: [Document the selected structure and reference the real directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
