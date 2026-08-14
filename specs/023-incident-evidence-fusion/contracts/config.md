# Contract: Incident Evidence Fusion Configuration

## Defaults

The first implementation adds only these flat keys to
`app/config.example.json`:

```json
{
  "incident_fusion_enabled": false,
  "incident_fusion_context_hours": 24,
  "incident_fusion_fleet_window_seconds": 60
}
```

Existing keys remain authoritative for source freshness and action attribution:

```json
{
  "diagnosis_stale_seconds": 900,
  "diagnosis_firmware_window_hours": 24,
  "diagnosis_collector_stale_seconds": 3600,
  "restart_attribution_window_seconds": 900
}
```

## Validation

| Key | Type | Accepted range | Invalid-value behavior |
| --- | --- | --- | --- |
| `incident_fusion_enabled` | boolean | `true` or `false` | disable fusion |
| `incident_fusion_context_hours` | finite number | 1 to 168 | use default 24 and log one config warning |
| `incident_fusion_fleet_window_seconds` | finite integer | 30 to 300 | use default 60 and log one config warning |

The existing diagnosis and attribution keys keep their current validation and
defaults. No environment variable overrides these fusion keys in the first
release.

## Runtime Meaning

- `false`: preserve current `/diagnose` and dashboard behavior; do not generate
  or persist new assessments.
- `true`: enable only on-demand read-only assessment generation and shared
  rendering.
- Changing the flag does not modify the source schema, miner state, action
  policy or scheduled collectors.

The ruleset version is not configurable. It is a code-owned audit identifier so
operators cannot silently change the meaning of persisted assessments.

## Safety And Rollback

Invalid configuration fails closed to the existing diagnosis path. Disabling
the feature is the complete runtime rollback; additive tables remain readable
and no source evidence is deleted.
