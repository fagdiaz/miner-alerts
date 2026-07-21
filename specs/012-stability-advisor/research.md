# Research: Stability Advisor

## Robust Baseline

**Decision**: Median plus scaled median absolute deviation (MAD), with per-metric
relative and absolute minimum bands.

**Rationale**: Miner telemetry contains spikes, missing values, and state changes.
Median/MAD resists outliers; minimum bands avoid classifying harmless noise when
the observed MAD is zero.

**Alternatives considered**: Mean/standard deviation was rejected as more
sensitive to incidents. Machine-learning models were rejected because the fleet
and history are small and explainability is a safety requirement.

## Action Policy

**Decision**: Advisory only.

**Rationale**: Historical data is not yet sufficient to prove that adaptive
baselines are safe as reboot gates. The same evidence can be reviewed first in
Telegram and the dashboard.

## Voltage Meaning

**Decision**: Treat `chain_voltage_mv_avg` as board-side firmware telemetry only.

**Rationale**: It can reveal drift relative to the miner's own baseline but does
not measure AC input voltage or prove mains fluctuation.

## Interface

**Decision**: Reuse SQLite, Telegram polling, and static HTML; add no framework.

**Rationale**: This delivers operator value with no listener, authentication
surface, dependency, or second source of truth.
