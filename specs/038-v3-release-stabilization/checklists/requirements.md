# Requirements Checklist: Spec 038 (V3 Core Concurrency & Release Stabilization)

## Concurrency & Synchronization
- [ ] CHK001 All accesses to `snooze_until_ts` in auto-reboot decisions are synchronized with `state_lock`.
- [ ] CHK002 All reads of `MinerState` in Telegram commands `/fans`, `/efficiency`, `/presets`, `/snooze`, `/digest` acquire `state_lock`.
- [ ] CHK003 `save_state()` reads state copies or acquires `state_lock` during snapshot construction.
- [ ] CHK004 `pending_reboot_tokens` dict is guarded against concurrent modification during callback dispatch.
- [ ] CHK005 `answer_callback_query()` has a tight network timeout (<= 3.0s) and never blocks getUpdates polling.

## SQLite Concurrency
- [ ] CHK006 All analytical queries in V3 commands open SQLite with `uri=True` and `mode=ro`.
- [ ] CHK007 All analytical queries specify an explicit timeout (<= 2.0s).
- [ ] CHK008 Every SQLite connection is guaranteed closed via `try ... finally: conn.close()`.

## Operational Safety & Soak
- [ ] CHK009 Production process `PID 38816` remains untouched during all test and audit activities.
- [ ] CHK010 Full test regression passes with zero failures.
- [ ] CHK011 New concurrency test suite in `tests/test_v3_concurrency.py` passes deterministically.
