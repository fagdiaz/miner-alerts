# Data Model: Hashcore Capability Inventory

## ToolkitInstallation

- `inventory_version`: Artifact schema.
- `toolkit_version`: Installed vendor version.
- `executable_fingerprint`: Sanitized file identity/hash.
- `discovered_ts`: Inventory time.
- `discovery_status`: Complete, partial, missing or blocked.

## CommandCapability

- `name / aliases`: Discovered command identity.
- `usage_shape`: Sanitized syntax.
- `classification`: Read-only, mutating or unknown.
- `evidence_ref`: Help/doc/sample reference.
- `timeout_seconds`: Invocation bound.
- `integration_overlap`: Existing source comparison.

## InvocationSample

- `command_id`: Capability reference.
- `exit_code / duration_ms`: Behavior.
- `stdout_shape / stderr_shape`: Sanitized structure, not secrets.
- `timed_out`: Bounded result.

## Invariants

- Unknown is never executable in production.
- Raw secrets/addresses are never committed.
- Inventory never changes monitor action scope.
- Samples are tied to one Toolkit version.
