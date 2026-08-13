# Data Model: V2 Release Stabilization

## ReleaseCandidate

- `commit_id`: Exact code identity.
- `dependency_versions`: Python and optional stack locks.
- `schema_version`: EventStore compatibility.
- `config_example_hash`: Documented default identity.
- `created_ts`: Freeze time.

## ValidationResult

- `check_id / area`: Stable matrix identity.
- `command / environment`: Reproducible execution.
- `expected / observed`: Outcome evidence.
- `status`: Pass, fail or blocked.
- `evidence_ref`: Sanitized artifact link.

## ReleaseBlocker

- `priority`: P0 or P1.
- `owner_spec`: Smallest affected scope.
- `containment`: Immediate safety response.
- `retest_ids`: Required matrix checks.
- `closed_ts`: Evidence-backed closure.

## Invariants

- Candidate identity does not change during a successful soak.
- Any code change resets affected validation and observation clocks.
- Blocked evidence cannot be marked pass.
- Release approval requires zero open P0/P1 blockers.
