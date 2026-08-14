# Evidence: Prometheus Metrics And Grafana

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Specs 021 and 022 stable heartbeat and acquisition-quality contracts.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Mapped current heartbeat, miner, episode, Telegram, collector and Spec 022
  acquisition evidence to one atomic sanitized snapshot.
- Defined exact schema-v1 fields, 26 metric families, finite labels and the
  `23 + 20 * miners` series formula (103 current; 128 test ceiling).
- Defined stale/malformed behavior that exports snapshot health only, never old
  miner values, plus loopback/internal-only container boundaries.
- Defined disabled-by-default configuration, prohibited mounts and full-stack
  outage rollback. No runtime source, config, service or container changed.

## Required Evidence Before Completion

- Metric contract and cardinality count.
- Secret/address scan of snapshot and scrape.
- Compose config and pinned image versions.
- CPU, memory, scrape time and disk growth.
- Snapshot write latency, stale/malformed health-only proof and prohibited-mount audit.
- Dashboard screenshots/queries and D+1/D+3 notes.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
