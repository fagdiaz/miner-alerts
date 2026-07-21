# Research: Mining Quality Intelligence

## Observed Production Evidence

A read-only API 4028 capture on 2026-07-20 confirmed four responding S19j Pro
miners with three active boards each. The deployed payloads expose:

- `Accepted`, `Rejected`, `Stale`, `Elapsed`, and summary hardware errors.
- `chain_state1..3`, `chain_fault1..3`, `chain_hw1..3`.
- Chain consumption, chain voltage, frequency, temperatures, fans, and PWM.

The sanitized snapshots are local under ignored `diagnostics/` paths. They are
evidence, not committed fixtures.

## Decisions

### Use Interval Deltas

Accepted/rejected/stale values are cumulative. The useful signal is the delta
between comparable samples in one uptime epoch. Lifetime percentages can hide a
recent problem and counter resets can otherwise create invalid negative rates.

### Keep Analysis Deterministic

Median/MAD already covers long-term operating bands. Quality classification uses
explicit interval percentages and current chain evidence because those outputs
must be explainable during an incident.

### Do Not Add Miner IO

The monitor already receives `summary` and `stats`. Reusing those responses avoids
latency and avoids turning Telegram diagnostics into a live control dependency.

### Defer Firmware Log Collection

Vnish documents useful fault categories, and Hashcore Toolkit exposes diagnostic
report functionality, but the deployed firmware log transport has not been
verified. No API endpoint, SSH path, or scraper is introduced until local evidence
confirms the supported source.

## Technology Choice

The existing Python + SQLite + static HTML stack remains appropriate. It provides
durable evidence, deterministic tests, Windows compatibility, and a migration path
to Prometheus/Grafana later without adding an operations platform before metric
semantics stabilize.
