# Data Model: Schema V2

## telemetry_samples Additions

Additive nullable fields preserve all schema-v1 rows:

| Field | Type | Meaning |
| --- | --- | --- |
| `max_temp_c` | REAL | Highest valid firmware-reported temperature |
| `chain_voltage_mv_avg` | REAL | Average `chain_vol*` value; board evidence, not AC input |
| `chain_power_w_total` | REAL | Sum of valid `chain_consumption*` values |
| `frequency_mhz_avg` | REAL | Average valid `freq_avg*` value |
| `hw_errors_total` | INTEGER | Sum of valid `chain_hw*` counters |
| `fan_rpm_max` | INTEGER | Maximum valid `fanN` RPM |
| `fan_pwm_percent` | REAL | Firmware-reported fan PWM |
| `diagnostic_flags_json` | TEXT | Bounded JSON array of conservative evidence labels |

## reboot_decisions

| Field | Type | Constraints / Meaning |
| --- | --- | --- |
| `id` | INTEGER | Primary key |
| `evaluated_ts` | REAL | Required epoch timestamp |
| `miner_key` | TEXT | Required stable monitor key |
| `miner_name` | TEXT | Required display name |
| `host` | TEXT | Required miner host |
| `result` | TEXT | Required gate/action result |
| `state` | TEXT | Current state-machine state |
| `responded` | INTEGER | Current API response status |
| `rate_ths` | REAL | Current rate or null |
| `threshold_ths` | REAL | Configured threshold |
| `low_elapsed_seconds` | REAL | LOW duration in this process or null |
| `active_boards` | INTEGER | Existing policy board signal or null |
| `expected_boards` | INTEGER | Configured expected boards |
| `max_temp_c` | REAL | Normalized evidence |
| `chain_voltage_mv_avg` | REAL | Normalized board voltage evidence |
| `chain_power_w_total` | REAL | Normalized consumption evidence |
| `frequency_mhz_avg` | REAL | Normalized frequency evidence |
| `hw_errors_total` | INTEGER | Normalized HW counter total |
| `fan_rpm_max` | INTEGER | Normalized fan evidence |
| `startup_guard_active` | INTEGER | Existing gate state |
| `qa_mode` | INTEGER | Existing QA mode |
| `cooldown_remaining_seconds` | REAL | Existing cooldown evidence or null |
| `window_count` | INTEGER | Purged existing reboot-window count |
| `window_seconds` | INTEGER | Existing configured window |
| `details_json` | TEXT | Bounded non-secret context |

Indexes:

- `(miner_key, evaluated_ts DESC)` for `/why <miner>`.
- `(evaluated_ts DESC)` for latest global decision and retention.
- `(result, evaluated_ts DESC)` for offline summaries.

## Invariants

- Null means unknown; zero is a real observed value.
- Raw stats/pools/version payloads are never stored.
- Decision rows cannot be read by action policy.
- Existing operational event IDs and sample rows survive migration.
