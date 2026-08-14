# Data Model: Hashcore Capability Inventory

## ToolkitInstallation

- `inventory_version`: Artifact schema.
- `toolkit_version`: Sanitized Windows PE product/file version.
- `wrapper_basename / executable_basename`: Names without parent directories.
- `wrapper_size_bytes / executable_size_bytes`: Static file sizes.
- `wrapper_sha256 / executable_sha256`: Full artifact-binding hashes.
- `wrapper_shape`: Fixed classification such as `argv_passthrough`.
- `discovered_at_utc`: Inventory time.
- `discovery_status`: Complete, partial, missing or blocked.
- `mode`: `metadata_only` or `reviewed_invocation`.

Absolute paths and working-directory values are never serialized.

## InvocationApproval

- `invocation_id`: Stable allowlist key.
- `wrapper_sha256 / executable_sha256`: Exact installation binding.
- `argv`: Fixed literal argument vector.
- `vendor_evidence_ref / evidence_digest`: Review provenance.
- `reviewed_at_utc / reviewed_by`: Approval audit fields.
- `timeout_seconds`: Integer 1 through 10.
- `expected_exit_codes / expected_output_shape`: Finite behavior contract.

## CommandCapability

- `name / aliases`: Evidence-derived command identity.
- `usage_shape`: Sanitized syntax.
- `classification`: Read-only, mutating or unknown.
- `evidence_ref`: Help/doc/sample reference.
- `timeout_seconds`: Invocation bound.
- `integration_overlap`: Existing source comparison.
- `classification_reason`: Stable reason code, including contradictory or
  insufficient evidence.

## InvocationSample

- `invocation_id / command_id`: Approval and capability references.
- `installation_fingerprint`: Exact wrapper/executable hash pair.
- `exit_code / duration_ms`: Behavior.
- `stdout_shape / stderr_shape`: Sanitized structure, not secrets.
- `stdout_bytes / stderr_bytes`: Captured sizes, each at most 65,536.
- `stdout_truncated / stderr_truncated`: Explicit truncation flags.
- `sanitization_counts`: Redaction counters by finite category.
- `timed_out`: Bounded result; timeout performs no retry.

## IntegrationCandidate

- `capability_id`: Read-only capability reference.
- `evidence_gap`: Missing evidence not already supplied by API 4028, Vnish,
  EventStore or diagnostics.
- `overlap_sources`: Existing sources compared.
- `operator_value / reliability / implementation_cost`: Finite rankings.
- `decision`: `accept_for_future_spec`, `duplicate`, `blocked` or `reject`.
- `future_spec_prerequisite`: Required for every accepted candidate.

## Invariants

- Unknown is never executable in production.
- Metadata-only starts zero subprocesses.
- Allowlist absence or fingerprint mismatch starts zero subprocesses.
- Raw secrets/addresses are never committed.
- Inventory never changes monitor action scope.
- Samples are tied to one Toolkit version.
- One command has exactly one classification in an artifact.
- A changed installation invalidates all earlier approvals and samples.
