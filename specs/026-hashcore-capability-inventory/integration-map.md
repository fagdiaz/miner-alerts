# Integration Map: Hashcore Capability Inventory

## Runtime Boundary

Spec 026 is a standalone inventory. It does not import into, call from or modify
the production monitor. The only planned executable is
`tools/hashcore_inventory.py`; `app/miner_monitor.py` is inspected as an
invariant target only.

Current production seams that must remain unchanged:

| Seam | Current role | Spec 026 rule |
| --- | --- | --- |
| `_hashcore_cli_path` | Resolves the configured wrapper/CLI path. | Inspect only; do not change resolution. |
| `run_hashcore_discovery` | Existing fallback for missing action templates. | Record as baseline; do not call or expand it. |
| `run_hashcore_cli` | Executes configured `reboot`/`restart` actions. | Preserve QA gate, templates, timeout and callers byte/semantically. |
| Telegram `selftest` Hashcore block | Runs the existing version/help probe. | Record as baseline; no new invocation is wired into selftest. |
| Auto/manual reboot callers | Existing action authority. | No new capability may be called from these paths. |

## Proven Local Installation Baseline

A static inspection on 2026-08-13, without starting the wrapper or executable,
established:

- configured wrapper exists and is named `toolkit_cli.bat`;
- wrapper size is 181 bytes and SHA-256 prefix is `2c204d87`;
- wrapper delegates arbitrary `%*` arguments to `hashcore-toolkit.exe cli` and
  therefore is not an allowlist or safety boundary;
- executable exists, is 808,960 bytes and has SHA-256 prefix `9db18421`;
- Windows file metadata reports Hashcore Toolkit `1.6.0+167`;
- configured production templates exist for exactly `reboot` and `restart`.

No full path, settings value, miner address, credential or raw config value is
part of this baseline. These facts prove installation identity only. They do
not prove that `help`, `version` or any other argument is side-effect free.

## Two-Phase Discovery

### Phase A - Metadata Only (Default)

Allowed filesystem reads:

1. Resolve the configured wrapper path without printing it.
2. Read wrapper/executable bytes for size and SHA-256.
3. Read Windows PE version metadata.
4. Parse the wrapper only to describe its forwarding shape.

This phase starts zero subprocesses, reads no settings payload and performs no
network IO. Missing files, unsupported metadata and wrapper changes are stable
results rather than reasons to guess commands.

### Phase B - Reviewed Invocation (Blocked Today)

Phase B is unavailable until `contracts/discovery-allowlist.md` can be populated
from vendor documentation or a separately supplied trusted sample. Each entry
is bound to the full wrapper and executable SHA-256. A filename, semantic guess
or an invocation already present in production code is not sufficient proof.

An approved invocation:

- contains a fixed argv vector and no miner/settings arguments;
- uses `shell=False`, `stdin=DEVNULL` and Windows no-window flags;
- runs at most once, with no retry, for at most 10 seconds;
- captures no more than 64 KiB from stdout and 64 KiB from stderr;
- contributes to a total inventory runtime ceiling of 120 seconds;
- is sanitized before any normalized artifact is written;
- is invalidated if either installation fingerprint changes.

For a `.bat` wrapper, any `cmd.exe` adapter must be fixed by code and receive
only allowlisted literal arguments. No shell string, user fragment, miner token
or settings path may be concatenated.

## Data Flow

```text
local config (path only)
        |
        v
metadata reader ----> installation fingerprint ----> sanitized inventory
        |                         |
        |                         +---- mismatch/absent allowlist --> BLOCKED
        v
reviewed allowlist -- exact match --> bounded process sample --> sanitizer
                                                        |
                                                        v
                                      capability classification + overlap
```

Raw config and process output remain local and ignored. Only normalized records
described by `data-model.md` may be committed.

## Existing Source Overlap

Every read-only candidate must be compared against these current sources before
it is accepted:

| Existing source | Current evidence |
| --- | --- |
| API 4028 | Summary, stats, pools and version responses used by monitor/diagnostics. |
| Vnish parsing | Firmware events, chain state, PSU codes and transition evidence. |
| SQLite EventStore | Samples, transitions, incidents, actions, decisions and collector runs. |
| Diagnostics tools | Read-only snapshots, incident reports and stability profiles. |

Duplicate data is not an integration candidate unless it provides a measured
reliability, freshness or diagnostic advantage. Any accepted candidate receives
a separate spec; no candidate is implemented by Spec 026.

## Failure Boundary

- Missing installation: `missing`, no process.
- Metadata unavailable: `partial`, no process.
- Missing/invalid/mismatched allowlist: `blocked`, no process.
- Timeout or non-zero exit: one bounded sample, capability remains `unknown`.
- Sanitization uncertainty: artifact is not promoted.
- Any evidence of a miner target or mutation: stop inventory and classify the
  capability `mutating` or `unknown`.
