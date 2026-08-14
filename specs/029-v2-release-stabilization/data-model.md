# Data Model: V2 Release Stabilization

## ReleaseCandidate

- `commit_id`: Exact code identity.
- `branch / tracked_tree_clean`: Git identity and hygiene.
- `runtime_payload_sha256 / payload_entries`: Observation-controlling digest.
- `dependency_versions`: Python and optional stack locks.
- `schema_version`: EventStore compatibility.
- `config_example_hash`: Documented default identity.
- `service_identities / task_identities`: Sanitized SCM/task definitions.
- `dependency_dispositions`: Exactly one terminal state per Spec 021-028.
- `prior_known_good`: Runtime/service rollback identity.
- `created_at_utc`: Freeze time.

## ValidationResult

- `check_id / area`: Stable matrix identity.
- `command / environment`: Reproducible execution.
- `expected / observed`: Outcome evidence.
- `candidate_commit / runtime_payload_sha256`: Identity under test.
- `started_at_utc / completed_at_utc / duration_ms`: Timing.
- `status`: pass, fail, blocked or not_applicable.
- `blocker_id`: Required for fail; disposition evidence required for N/A.
- `evidence_ref`: Sanitized artifact link.

## ReleaseBlocker

- `priority`: P0 or P1.
- `owner_spec`: Smallest affected scope.
- `containment`: Immediate safety response.
- `retest_ids`: Required matrix checks.
- `closed_ts`: Evidence-backed closure.
- `opened_at_utc / last_seen_at_utc / closed_at_utc`: Lifecycle.
- `runtime_payload_sha256`: Affected candidate identity.
- `affected_check_ids`: Stable R001-R025 IDs.

## DailyObservation

- `day_index`: Integer 1 through 7.
- `window_start_utc / window_end_utc`: Continuous covered interval.
- `runtime_payload_sha256`: Must match candidate.
- `service / heartbeat / workers / watchdog / collector`: Finite health summary.
- `episode_counts / action_decision_counts / telegram_delivery_counts`: Bounded
  aggregate evidence; no payloads.
- `evidence_gaps / blocker_ids`: Explicit lists.
- `status`: pass, fail or blocked.

## ReleaseDecision

- `decision`: approve or block.
- `candidate_commit / runtime_payload_sha256`: Final identity.
- `matrix_digest / observation_digest / restore_manifest_digest`: Evidence bind.
- `open_blocker_ids / missing_check_ids`: Must both be empty for approve.
- `decided_at_utc / reviewer`: Audit identity.

## Invariants

- Candidate identity does not change during a successful soak.
- Any code change resets affected validation and observation clocks.
- Docs/evidence-only changes preserve observation only with unchanged runtime digest.
- Blocked evidence cannot be marked pass.
- Release approval requires zero open P0/P1 blockers.
- Every R001-R025 row has exactly one terminal result.
- Daily observations cover one contiguous 168-hour interval.
