# Research: Irregular Miner Episodes

## Decision 1 - Model notification history as episodes

**Decision**: One episode starts when confirmed state leaves OK, accumulates irregular transitions/restart evidence, and closes on confirmed OK.

**Rationale**: The operator thinks in incidents, while the current implementation emits unrelated state and restart messages. A single timeline directly supports reminders, recovery summaries and detail.

**Alternatives considered**: Increase individual alert timers; keep separate state/restart/outage coordinators. Both preserve contradictory timing and duplicate messages.

## Decision 2 - Preserve the state machine and render live status separately

**Decision**: `/status` uses the current response, rate and board sample. Confirmed state remains available only to determine whether a healthy sample is still `RECUPERANDO`.

**Rationale**: `recovery_successes=2` intentionally retains OFFLINE/LOW for one healthy sample. Showing that retained label beside a live 97 TH/s rate is presentation error, not state-machine error.

**Alternatives considered**: Remove recovery hysteresis or force state OK on one sample. Both increase false recovery risk and alter core behavior.

## Decision 3 - Use an episode-age reminder schedule

**Decision**: Notify at total ages 5, 10, 15, 30, 60 and 120 minutes, then hourly.

**Rationale**: This provides the requested three five-minute checks, then widening intervals without silence. Absolute ages are deterministic across delayed polling cycles.

**Alternatives considered**: Fixed five-minute reminders forever (too noisy); 15/30-minute defaults (allowed the observed outage to be forgotten).

## Decision 4 - Short bounded grouping replaces the restart delay

**Decision**: Use the same 30-second fleet grouping horizon for initial state/restart/recovery episode notices.

**Rationale**: The current 180-second restart coalescer is the direct source of the three-minute delay. Thirty seconds covers one normal polling interval and still groups adjacent miners.

**Alternatives considered**: Immediate per-miner restart messages (fleet spam); retain 180 seconds (fails operator requirement).

## Decision 5 - Reuse SQLite schema v5

**Decision**: Keep using `operational_events` for state transitions, restart incidents and action outcomes; add only a bounded related-timeline query.

**Rationale**: All required facts are already persisted with timestamp, miner, state, rate, uptime and action attribution. A new table would duplicate facts and require unnecessary migration risk.

**Alternatives considered**: New episode table; persist notification coordinator internals in `state.json`. Both add state synchronization concerns without improving canonical evidence.

## Decision 6 - Add click-safe read-only incident detail

**Decision**: `/e<ID>` maps to the existing `/event <id>` detail path and includes bounded related events.

**Rationale**: Telegram command links containing spaces do not reliably carry the ID when tapped. The alias is read-only and follows the existing `/rb<ID>` and `/c<code>` pattern.

**Alternatives considered**: Inline buttons/callback queries (new Telegram architecture); print full timelines in every alert (chat noise).

## Runtime Evidence Behind The Design

- Real config: `poll_seconds=30`, `fails_before_alert=1`, `recovery_successes=2`.
- `restart_notification_coalesce_seconds` defaults to 180 seconds.
- Miner 25 persisted `OK -> OFFLINE`, restart detection, `OFFLINE -> HASHBOARD -> LOW -> OK`; SQLite already contains the complete sequence.
- API read code returns `rate=None` on no response. The contradictory status occurs when live rate has recovered but confirmed state remains OFFLINE for hysteresis.
