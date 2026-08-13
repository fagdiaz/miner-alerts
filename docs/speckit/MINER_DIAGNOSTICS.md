# Miner Diagnostics Strategy

**Last reviewed**: 2026-08-13
**Future contracts**: Specs 021-024 in `docs/speckit/SPEC_PROGRAM.md`

## Objective

Determine why a miner is unhealthy before deciding whether to reboot it. For
S19j Pro miners running Vnish-style firmware, the useful diagnosis is usually
not just "hashrate below threshold"; it is the combination of hash, boards,
temperature, pool state, firmware state, recent logs, and power symptoms.

## Current Data Sources In The Repo

The monitor already reads:

- `summary`: hashrate, elapsed, response status.
- `stats`: active board hints and temperatures.
- `pools`: pool URL and worker/user.
- `version`: firmware hints, including Vnish/ASIC.to detection.
- Hashcore Toolkit CLI: currently configured for `reboot` and `restart`.

Acquisition roles are intentionally different:

| Source | Mode | Role | Must not be used as |
| --- | --- | --- | --- |
| API 4028 `summary`/`stats` | 30-second polling | Current state, rate, uptime and boards. | Historical cause certainty. |
| Vnish log WebSockets | Bounded scheduled collection | Firmware transitions and warnings. | Sole proof that a miner is currently healthy. |
| SQLite | Local persisted queries | Timeline, trends and decisions. | Direct auto-reboot trigger. |
| Hashcore CLI | On-demand | Confirmed actions and future proven diagnostics. | Background monitoring transport. |
| PDU/UPS/sensor | Not selected yet | Future AC voltage/current/power evidence. | Inference from hashboard voltage. |

Production board counting recognizes both legacy cgminer fields and Vnish
`chain_acn1..N`, scanning all `STATS` entries because deployed Vnish payloads
place chain evidence after a metadata entry. Unknown board evidence remains
unknown rather than being treated as zero.

The read-only collector in `tools/miner_diagnostics.py` can export a sanitized
snapshot of the same API 4028 sources without touching the running monitor:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.json --out diagnostics\\latest
```

It writes:

- `summary.md`: operator-readable matrix.
- `snapshot.json`: sanitized structured evidence.

Use `--dry-run` to validate config parsing without contacting miners.

The baseline analyzer consumes one snapshot or a diagnostics folder:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline
```

It writes:

- `baseline.md`: operator-readable sweet-spot table.
- `baseline.json`: structured baseline for future comparison.

## Diagnosis Layers

Every layer must carry `observed_ts`, source and freshness. Missing evidence is
`unknown`, not healthy and not zero.

### Layer 1 - Signal Quality

Classify the input before acting:

- Fresh OK signal.
- Fresh LOW signal.
- OFFLINE/no response.
- STALE snapshot.
- Invalid or missing rate.
- HASHBOARD issue.

Action policy: invalid or stale signal should not be treated as a reboot candidate.

Planned acquisition work will add separate ages for the last attempt, last
successful sample and last completed fleet tick. This prevents a live process
with a stalled polling loop from presenting old data as current.

### Layer 2 - Miner Health

Inspect miner-side state:

- Active boards vs expected boards.
- Board/chip temperature.
- Fan behavior when available.
- Hashrate per board when available.
- Pool connectivity and reconnect patterns.
- Firmware string and Vnish hints.

Action policy: missing board or overheating may need a different response than
low aggregate hash.

### Layer 3 - Firmware Activity

For Vnish, determine whether the firmware is actively tuning or recovering:

- Autotune/profile change in progress.
- Voltage/frequency changes.
- Chain restart.
- Miner process restart.
- Watchdog action.
- Pool reconnect.

Action policy: avoid reboot while firmware is already correcting the condition,
unless the condition persists beyond the configured safety window.

### Layer 4 - Electrical Context

Do not assume the miner exposes AC input voltage. Some firmware may expose PSU
or board voltage fields; some may not. If voltage matters operationally, confirm
the available data source.

Possible sources:

- Vnish/API stats fields, if present.
- Miner logs, if they include PSU warnings.
- PDU/UPS/smart meter API.
- Manual voltage readings imported as evidence.

Action policy: suspected voltage fluctuation should be logged as diagnosis, not
used alone as a reboot trigger.

Electrical-source discovery is scheduled before implementation. Prefer a real
device protocol already supported by the selected PDU/UPS/sensor (SNMP, Modbus
TCP, vendor HTTP or MQTT); do not select a protocol before selecting the source.

## Episode And Root-Cause Correlation

Spec 020 groups current state transitions into bounded OK-to-OK episodes. The
next diagnosis layer must enrich those episodes without rewriting their facts:

- `observed`: direct rate, board, uptime, pool, firmware or electrical evidence;
- `suspected`: time-correlated but not independently confirmed condition;
- `confirmed`: direct source evidence with compatible timestamps.

Fleet-wide simultaneous symptoms increase diagnostic priority but do not prove
power failure. A full timeline remains read-only and cannot authorize reboot.

## Sweet Spot Model

Create a per-miner profile from observed stable operation:

- Stable TH/s range.
- Temperature range by board.
- Board count.
- Frequency/voltage profile if available.
- Error/reject rate if available.
- Last stable firmware profile.
- Reboot/restart history.

The sweet spot should be descriptive first. It should not automatically tune or
change firmware settings until evidence proves the model is reliable.

Initial sweet spot workflow:

1. Capture repeated read-only snapshots during stable operation.
2. Capture snapshots when Telegram reports LOW/OFFLINE/HASHBOARD.
3. Build a baseline with `tools/diagnostics_baseline.py`.
4. Compare TH/s, active boards, temps, pool status, firmware hint, and candidate
   Vnish fields.
5. Promote only repeatable patterns into reboot policy changes.

## Reboot Decision Matrix

Prefer "observe" when:

- Data is stale or invalid.
- LOW has not been sustained.
- Vnish appears to be autotuning or restarting chains.
- Pool issue affects multiple miners.
- Power anomaly is suspected but not confirmed.

Prefer "restart miner service" when:

- Firmware is reachable.
- API responds.
- Boards are present.
- Hash is degraded but no hardware/power symptom is visible.

Prefer "reboot" only when:

- LOW is sustained in the current process execution.
- Startup guard is inactive.
- Cooldown/window allows it.
- QA guardrails allow action.
- Signal is fresh and actionable.
- No safer firmware-level recovery is in progress.

## Evidence To Capture

For each candidate reboot:

```text
miner=<id>
state=<OK|LOW|OFFLINE|HASHBOARD>
rate_ths=<value>
threshold_ths=<value>
responded=<true|false>
active_boards=<n>
temps=<list>
pool_status=<summary>
firmware_hint=<value>
vnish_event=<last relevant event>
power_context=<available|not_available|suspected_anomaly>
blocked_by=<reason or none>
action=<observe|restart|reboot>
```

## Delivery Order

1. Monitor heartbeat and stale-data detection.
2. Measured staggered/adaptive acquisition.
3. Episode/Vnish/pool/fleet evidence fusion.
4. Electrical source discovery and optional adapter.
5. Prometheus/Grafana export after metric semantics stabilize.

Dates and mandatory observation windows are maintained in
`docs/speckit/DELIVERY_PLAN.md`.
