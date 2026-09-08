# Concurrency Contract: Spec 038

## Invariants:
1. **State Atomicity**: No thread may mutate `MinerState` attributes without holding `state_lock`.
2. **Reboot Immunity**: If `state.snooze_until_ts > now_ts`, NO auto-reboot action may be scheduled or executed under any race condition.
3. **Single-Use Reboot Tokens**: A reboot token (`rb_cfm:<token>`) must be deleted from `pending_reboot_tokens` immediately upon first lookup before action execution, preventing double-clicks from issuing twin reboots.
4. **Read-Only Database Access**: Auxiliary commands and tools may never open `data/miner_alerts.db` with write permissions. Read connections must specify `?mode=ro` and timeout <= 2.0s.
5. **Production Soak Invariant**: The production monitor `PID 38816` must never be killed, interrupted, or restarted during test runs.
