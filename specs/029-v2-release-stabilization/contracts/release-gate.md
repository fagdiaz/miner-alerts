# Contract: V2 Release Gate

## Purpose

Define feature freeze, regression, activation, restore, observation and documentation requirements for release approval.

## Inputs

- Accepted/blocked per-spec evidence.
- Frozen candidate identity and clean environment.
- Controlled Windows maintenance window and backup destination.

## Outputs

- Complete regression matrix.
- Runtime/restore/documentation evidence bundle.
- Explicit release approve or block decision.

## Failure And Safety Contract

- P0/P1 blocks release.
- No new feature during stabilization.
- No production completion without observed service and actions.

## Compatibility

- Prior known-good rollback identity is recorded.
- Conditional no-build/blocked specs remain truthful and do not block when their gates pass.
