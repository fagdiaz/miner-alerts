# Research: V2 Release Stabilization

## Baseline Findings

- Compilation alone cannot validate Telegram delivery, service recovery, polling progression or action safety.
- Runtime evidence and checked tasks can diverge; evidence must win.
- The system now has several auxiliary read-only components that require outage-isolation testing.
- Backup restoration and documentation consistency are cross-feature release concerns.
- Git commit alone is too broad for soak continuity because evidence/docs closeout
  may advance it; a deterministic runtime-payload digest separates deployed
  behavior from documentation identity.
- A 72-hour soak plus a seven-day review is ambiguous unless modeled as one
  continuous 168-hour window with the 72-hour gate as an intermediate checkpoint.

## Decisions

1. Create a dedicated final stabilization spec instead of hiding closeout in the roadmap.
2. Freeze features and allow only blocker fixes with focused regression.
3. Require 72-hour soak plus a final seven-day review.
4. Treat blocked/no-build discovery outcomes as valid only when evidence is complete.
5. Require exactly one terminal disposition per dependency; generic incomplete
   or observation-pending states cannot enter freeze.
6. Use stable R001-R025 matrix IDs so each invariant has named evidence.
7. Use one 168-hour observation with seven daily reports and a 72-hour checkpoint.
8. Let docs-only commits preserve elapsed time only under an unchanged runtime
   payload digest; runtime/config/schema/service changes reset affected clocks.
9. Keep rollback runtime-only and preserve live state/SQLite and all safety gates.

## Rejected Or Deferred Alternatives

- Rolling release immediately after the last feature merge.
- Using checked tasks as proof of activation.
- Adding cleanup/refactors during stabilization.
- Skipping restore because backup creation succeeded.
- Restarting a soak for prose-only evidence edits when runtime bytes are unchanged.
- Preserving soak time after a runtime/config/service definition change.
- Treating an incomplete spec as deferred or blocked without explicit gate evidence.
- Exercising a real Hashcore action merely to prove release safety.

## External Validation Sources

- Project constitution: .specify/memory/constitution.md
- Program gates: docs/speckit/SPEC_PROGRAM.md
- Windows service recovery model: https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_failure_actionsw
- SQLite backup safety: https://www.sqlite.org/howtocorrupt.html
