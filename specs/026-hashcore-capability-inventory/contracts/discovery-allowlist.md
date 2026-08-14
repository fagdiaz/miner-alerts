# Contract: Hashcore Discovery Allowlist

## Current State

**BLOCKED**. Static metadata proves the local installation identity, but no
trusted vendor source has yet established an invocation as side-effect free.
The allowlist is intentionally empty. No Spec 026 process invocation is
approved by this document.

Existing `version`/help calls in production code are baseline behavior, not
evidence that a new inventory tool may invoke them.

## Approval Record

Each future approved entry must contain all fields:

| Field | Rule |
| --- | --- |
| `invocation_id` | Stable repository identifier. |
| `wrapper_sha256` | Exact full SHA-256, not a prefix. |
| `executable_sha256` | Exact full SHA-256, not a prefix. |
| `argv` | Fixed literal argument list; no placeholders. |
| `vendor_evidence_ref` | Versioned vendor document or trusted supplied sample. |
| `evidence_digest` | SHA-256 of the reviewed evidence. |
| `reviewed_at_utc` | UTC review time. |
| `reviewed_by` | Non-secret reviewer identifier. |
| `timeout_seconds` | Integer from 1 through 10. |
| `expected_exit_codes` | Explicit finite list. |
| `expected_output_shape` | Bounded structural description. |

## Rejection Rules

An entry is invalid and starts zero processes when:

- either fingerprint differs;
- an argument is not a fixed string;
- argv contains an address, miner token, settings/config path or credential;
- timeout is absent or exceeds 10 seconds;
- evidence is missing, mutable, version-ambiguous or only inferred from a
  command name;
- the command can discover, configure, restart, reboot, flash, tune, scan or
  otherwise touch a miner or Toolkit state;
- the wrapper/executable changed after review.

## Invocation Ceiling

At most one process may run per valid entry, sequentially, without retry. Total
inventory process time is capped at 120 seconds. Stdout and stderr are each
bounded to 64 KiB before sanitization; excess is marked truncated, never streamed
unboundedly into memory or artifacts.

## Promotion Gate

Adding the first allowlist entry requires review of this contract, deterministic
fixture tests, a no-process negative test for every rejection rule, and explicit
evidence that the invocation accepts no miner target. Until then, a blocked
metadata-only inventory is the correct complete outcome.
