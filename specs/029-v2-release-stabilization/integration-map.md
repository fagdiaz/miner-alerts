# Integration Map: V2 Release Stabilization

## Evidence Sources

Spec 029 owns no feature implementation. It consumes terminal per-spec evidence
and produces one release manifest, regression matrix, observation series and
approve/block decision.

| Source | Release use |
| --- | --- |
| Specs 021-028 `evidence.md` | Terminal disposition, rollout and observation references. |
| Git + Python environment | Candidate, clean-tree and dependency identity. |
| EventStore schema/config example | Compatibility/default hashes; no real config values. |
| Windows SCM/Scheduled Tasks | Sanitized service/task executable, arguments and recovery identity. |
| Watchdog/heartbeat/observer | Continuous monitor/process/worker evidence. |
| Backup manifest/restore report | Recoverability gate. |
| Test suites and QA fixtures | Deterministic invariant evidence. |
| Canonical docs | Status, operating and rollback agreement. |

## Runtime Payload Digest

The digest is a deterministic SHA-256 over sorted relative path, byte size and
file SHA-256 records for applicable runtime inputs:

- `app/**/*.py` excluding caches/runtime files;
- `tools/**/*.py` and applicable service/task `.ps1`/`.cmd` scripts;
- `app/config.example.json`;
- dependency/compose/Docker files for accepted components;
- templates/static assets for an accepted interface.

Specs, docs, tests, ignored artifacts and local real config/state/database/logs
are excluded. The exact included path list is itself stored in the manifest.
This digest controls observation continuity; Git commit remains the full release
identity and may move for evidence/docs-only commits.

## Terminal Dependency Dispositions

| State | Required proof | Runtime implication |
| --- | --- | --- |
| `accepted` | Tasks, rollout and required observation complete. | Feature rows mandatory. |
| `blocked_external` | Contract-complete discovery plus named unavailable external dependency and safe blocked behavior. | Implementation rows N/A; blocked boundary row mandatory. |
| `no_build` | Decision gate demonstrates existing surfaces satisfy requirements. | Conditional files/services absent. |
| `deferred` | Explicit program decision, rationale, risk acceptance and no partial activation. | No implementation represented in release. |

`planned`, `in_progress`, `observation_pending`, missing evidence and generic
`blocked` are not terminal and prevent freeze.

## Activation Sequence

1. Confirm terminal dependencies, no open P0/P1 and approved maintenance window.
2. Freeze manifest and prior known-good rollback/service/SCM identities.
3. Complete automated/QA rows R001-R021 and release-candidate backup/restore.
4. Set a bounded watchdog maintenance lease.
5. Perform one controlled service activation; capture R022 and clear/expire lease.
6. Execute read-only smoke and auxiliary isolation R023.
7. Start continuous 168-hour observation; close R024 at hour 72 and R025 at or
   after hour 168 only if all seven daily reports are present.

No real Hashcore action is required to approve release. Dangerous paths are
validated through QA blocks, mocks/fixtures and existing controlled evidence.

## Rollback Boundary

Before activation record:

- prior runtime payload/commit and venv dependency identity;
- prior service executable, arguments, account, start mode and failure actions;
- prior scheduled-task definitions for accepted auxiliary components;
- current database schema and backup manifest, without treating backup as an
  automatic rollback mechanism.

Rollback selects the prior runtime/service definitions, starts one process tree
and verifies mutex/startup guard/heartbeat. It does not replace `app/config.json`,
`state.json` or the live SQLite database; does not replay persisted LOW timers;
and does not weaken QA, startup, cooldown or confirmation gates. Data restore is
staging-first and manually approved under Spec 028.

## Auxiliary Isolation Matrix

Each accepted auxiliary component is stopped independently while the monitor is
observed:

- watchdog unavailable: monitor continues; liveness coverage visibly degrades;
- Vnish collector unavailable: monitor continues; collector becomes stale;
- exporter/Prometheus/Grafana unavailable: monitor and Telegram continue;
- backup task unavailable: monitor continues; backup health visibly fails;
- optional interface unavailable: monitor, Telegram and SQLite writer continue.

An auxiliary component must never own miner IO/actions unless already part of
the production monitor contract.
