# Contract: Adaptive Acquisition Configuration

## Safe Default

The feature is absent-or-disabled by default. Existing installations with none
of these keys continue through the current sequential path.

```json
{
  "adaptive_acquisition_enabled": false,
  "adaptive_acquisition_workers": 2,
  "adaptive_acquisition_timeout_seconds": 5.0,
  "adaptive_acquisition_deadline_seconds": 12.0,
  "adaptive_diagnostics_enabled": false,
  "adaptive_diagnostic_interval_seconds": 10.0
}
```

`poll_seconds` remains the sole nominal authoritative cadence. This contract
does not introduce a second cadence setting.

## Validation

| Key | Type | Accepted range | Invalid-value behavior |
| --- | --- | --- | --- |
| `adaptive_acquisition_enabled` | boolean | `true` or `false` | Treat as `false` and log one warning. |
| `adaptive_acquisition_workers` | integer | 1 to 4 | Use `2` and log one warning. |
| `adaptive_acquisition_timeout_seconds` | finite number | 1.0 to 10.0 | Use `5.0` and log one warning. |
| `adaptive_acquisition_deadline_seconds` | finite number | timeout to 30.0 | Use `12.0` and log one warning. |
| `adaptive_diagnostics_enabled` | boolean | `true` or `false` | Treat as `false` and log one warning. |
| `adaptive_diagnostic_interval_seconds` | finite number | 5.0 to 60.0 | Use `10.0` and log one warning. |

Unknown keys are ignored. Validation messages contain key names and sanitized
values only; no miner address, credential or Telegram secret is included.

## Runtime Rules

- `adaptive_acquisition_enabled=false` selects the sequential fallback before
  any executor or scheduled lease is created.
- `adaptive_diagnostics_enabled` has no effect while adaptive acquisition is
  disabled.
- Diagnostic probes are also disabled independently when their flag is false.
- No runtime environment variable overrides these values in the first release.
- Enabling or rollback requires a controlled service restart and the normal
  startup guard remains unchanged.
- Configuration changes do not migrate or rewrite `state.json` or SQLite.

## Request Budgets

- Authoritative: at most one summary plus one conditional stats request per
  configured miner in one current epoch.
- Diagnostic: at most one summary request per eligible miner in one diagnostic
  interval.
- Automatic retries: zero.
- Missed-epoch catch-up requests: zero.
- Manual Telegram command reads: outside these budgets and unchanged.
