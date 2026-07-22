# Data Model: Irregular Miner Episodes

## IrregularEpisode

- `miner_key`: stable existing miner identity.
- `name_display`, `host`: display metadata.
- `started_ts`: first confirmed irregular observation in this process.
- `current_state`: internal confirmed state (`LOW`, `OFFLINE`, `HASHBOARD`, `OK`).
- `responded`, `rate_ths`, `threshold_ths`: latest signal evidence.
- `active_boards`, `expected_boards`: latest board evidence.
- `history`: bounded ordered `EpisodeStep` collection.
- `detail_event_id`: first useful persisted transition or restart ID.
- `restart_event_ids`: bounded unique incident IDs.
- `initial_notice_sent`: whether the short coalesced opening notice was delivered.
- `reminder_index`: next absolute-age milestone.
- `closed_ts`: populated only after confirmed OK.

## EpisodeStep

- `occurred_ts`: transition/restart observation time.
- `kind`: `state` or `restart`.
- `label`: state name or restart label.
- `evidence`: bounded human-readable current evidence.
- `event_id`: optional persisted operational-event ID.

Consecutive identical state labels are updated rather than appended. History is capped to prevent unbounded process memory.

## EpisodeNotificationBatch

- `opened`: episodes whose short initial/update notice is due.
- `persistent`: active episodes whose next age milestone is due.
- `recovered`: closed episodes whose fleet grouping delay elapsed.

One batch produces at most one Telegram message per polling cycle.

## CurrentSignalView

Derived each tick from current data only:

1. no response -> `OFFLINE`, rate `N/A`;
2. response with missing boards -> `PLACAS active/expected`;
3. response with missing/non-finite rate -> `SIN DATOS`;
4. finite below-threshold rate -> `LOW`;
5. finite healthy rate plus retained irregular state -> `RECUPERANDO`;
6. finite healthy rate plus confirmed OK -> `OK` without warning label.

## OperationalTimeline

Read-only selection from existing `operational_events`:

- anchor: selected event ID;
- start: most recent `OK -> irregular` transition for the selected miner, bounded to six hours before the anchor;
- end: first later transition to OK, bounded to six hours after the anchor or current time;
- related rows: state transitions, restart detections and action outcomes for all miners in that bounded window;
- maximum rows: 50.

No schema migration is required.
