# Contract: Hashcore Capability Inventory

## Purpose

Define safe discovery, classification and the gate for future Toolkit integrations.

## Modes

- `metadata_only` is the default and starts zero subprocesses.
- `reviewed_invocation` requires an exact fingerprint-bound allowlist and an
  explicit operator flag. Absence or mismatch returns `blocked`.

## Inputs

- Local config used only to resolve wrapper and working directory paths.
- Installed wrapper/executable metadata and full SHA-256 fingerprints.
- Optional reviewed allowlist built from vendor-proven help/version evidence.

## Outputs

- Sanitized installation record with schema version and discovery status.
- Complete command classification table for every evidenced command.
- Ranked read-only integration candidates or explicit blocked result.

The canonical JSON artifact has these top-level keys only:

```text
schema_version
generated_at_utc
mode
status
installation
allowlist
invocations
capabilities
candidates
sanitization
```

`status` is one of `complete`, `partial`, `missing` or `blocked`. The artifact
never includes absolute paths, raw command output, settings content, hostnames,
IP addresses, credentials or Telegram identifiers.

## Installation Contract

`installation` records wrapper/executable basename, byte size, full SHA-256,
sanitized Windows file version and wrapper forwarding shape. It does not record
parent directories. A fingerprint change invalidates all invocation samples and
allowlist approvals from earlier artifacts.

## Invocation Contract

Every invocation record contains:

- stable invocation ID and allowlist evidence reference;
- exact sanitized argv literals;
- wrapper/executable fingerprints;
- start/end UTC, duration, exit code and timeout flag;
- bounded stdout/stderr byte counts and sanitized shape summaries;
- truncation and sanitization counters.

The process uses `shell=False`, stdin disabled, no-window creation, one attempt,
at most 10 seconds and at most 64 KiB captured per stream. It cannot contain a
miner, settings path, credential or user-supplied fragment.

## Classification Contract

Each evidenced command has exactly one classification:

- `read_only`: vendor evidence and sample both establish no state change;
- `mutating`: changes or may change device/toolkit state;
- `unknown`: evidence is absent, ambiguous, incomplete or contradictory.

`unknown` is prohibited under the same execution policy as `mutating`. Command
names such as `get`, `show`, `help` or `version` do not establish classification.

## Failure And Safety Contract

- No unknown or mutating new invocation.
- All calls timeout and use no-window execution.
- No invocation occurs without exact allowlist and fingerprint match.
- Any sanitization uncertainty blocks artifact promotion.
- No action-template change.

## Compatibility

- Existing reboot/restart flows remain byte/semantically unchanged.
- Future integrations reference inventory and use separate specs.
