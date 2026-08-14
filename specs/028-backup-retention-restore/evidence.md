# Evidence: Backup Retention And Restore

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Stable EventStore schema after Spec 023 and an operator-approved backup destination outside Git.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Defined the SQLite API-only transaction, 256-page batches, temporary/verified
  lifecycle, manifest v1 and atomic same-root promotion.
- Defined marked disjoint roots, containment/reparse guards, exclusive lock and
  pre/post free-space contract.
- Defined deterministic UTC union retention for 14 daily, 8 weekly and 12
  monthly verified generations; unknown/partial artifacts are never deleted by
  retention.
- Defined staging-only restore with hash, integrity, schema and exact table-count
  proof plus an explicit absence of any live replacement command.
- Defined disabled-by-default config and Scheduled Task read-back requirements.
  No runtime source, config, database, task or service changed.

## Required Evidence Before Completion

- Concurrent-write test and backup duration.
- Manifest, checksum and integrity output without real paths/data.
- Retention dry-run and actual owned-file report.
- Root marker, path containment, lock and free-space evidence.
- Scheduled task action and no-window proof.
- Successful staging restore drill and compatibility report.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
