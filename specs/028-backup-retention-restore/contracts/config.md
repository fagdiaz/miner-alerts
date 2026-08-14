# Contract: Backup Configuration

## Safe Example Defaults

```json
{
  "backup": {
    "enabled": false,
    "root": "",
    "staging_root": "",
    "minimum_free_bytes": 1073741824,
    "daily_generations": 14,
    "weekly_generations": 8,
    "monthly_generations": 12,
    "max_run_seconds": 300
  }
}
```

The monitor ignores this block. Only the standalone backup tool/installer reads
it.

## Validation

| Key | Accepted value | Invalid behavior |
| --- | --- | --- |
| `enabled` | boolean | disabled |
| `root` | non-empty absolute off-repo path when enabled | fail closed |
| `staging_root` | non-empty absolute path, disjoint from root/source/repo | fail closed |
| `minimum_free_bytes` | integer 268435456 to 1099511627776 | use 1 GiB default only in dry-run; scheduled run fails closed |
| `daily_generations` | integer 1 to 90 | fail closed |
| `weekly_generations` | integer 1 to 52 | fail closed |
| `monthly_generations` | integer 1 to 120 | fail closed |
| `max_run_seconds` | integer 60 to 1800 | fail closed |

No environment variable silently overrides paths or retention. Installer CLI
arguments may select the local config path but cannot embed secrets.

## Enablement

`enabled=false` is the committed example and default. Enabling requires an
operator-selected local root, successful manual backup, successful staging
restore and task read-back validation. Disabling stops future scheduled work but
does not delete verified artifacts.
