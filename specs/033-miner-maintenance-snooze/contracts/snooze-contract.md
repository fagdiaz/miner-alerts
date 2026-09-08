# Architecture & API Contract: Miner Maintenance Snooze (Spec 033)

**Specification**: [spec.md](../spec.md)  
**Status**: ACTIVE  

---

## 1. Data Contract

### `MinerState` Extension
```python
class MinerState:
    ...
    snooze_until_ts: Optional[float] = None
```

- When `snooze_until_ts is None`: miner is NOT snoozed.
- When `snooze_until_ts is not None`:
  - If `now_ts < snooze_until_ts`: miner is ACTIVE SNOOZE.
  - If `now_ts >= snooze_until_ts`: snooze is EXPIRED (equivalent to un-snoozed).

### Persistence Contract (`app/state.json`)
```json
{
  "states": {
    "S19JPRO-23|192.168.1.23:4028": {
      "state": "OFFLINE",
      "snooze_until_ts": 1757293200.0,
      ...
    }
  }
}
```

---

## 2. Command Grammar & Responses

### `/snooze <target> [minutes]`
- `<target>`: Miner ID (e.g. `23`, `s19jpro-23`), `all`, or `fleet`.
- `[minutes]`: Optional integer/float, default `60`. Minimum `1`, Maximum `1440` (24h).
- Response (Single):
  `🔕 Minero S19JPRO-23 silenciado durante 60m (hasta las 17:30). Alertas y autorreinicios suspendidos.`
- Response (Fleet/All):
  `🔕 Toda la flota silenciada durante 60m (hasta las 17:30). Alertas y autorreinicios suspendidos.`

### `/unsnooze <target>`
- Response (Single):
  `🔔 Supervisión reactivada para S19JPRO-23. Alertas y autorreinicios habilitados.`
- Response (Fleet/All):
  `🔔 Supervisión reactivada para toda la flota. Alertas y autorreinicios habilitados.`

### `/snoozed`
- Response (when empty):
  `🔔 No hay mineros silenciados actualmente. Todos están bajo supervisión activa.`
- Response (when active):
  ```text
  🔕 Mineros Silenciados:
  • S19JPRO-23: resta 45m (hasta las 17:30)
  • S19JPRO-24: resta 1h 15m (hasta las 18:00)
  ```

---

## 3. Callback Action Contract

- Trigger: `snz:<miner_id>:<minutes>`
- Max length: ≤ 32 bytes (well below 64 byte Telegram ceiling).
- Behavior:
  1. `answerCallbackQuery(bot_token, cb_id, text=f"🔕 {miner_name} silenciado por {minutes}m")`
  2. Sets `snooze_until_ts = now_ts + (minutes * 60)` in `states[key]`.
  3. `edit_message_reply_markup(bot_token, chat_id, message_id, build_settled_keyboard(f"🔕 Silenciado ({minutes}m)"))`
  4. Calls `save_state()`.

---

## 4. Safety Suppression Invariants

1. **Auto-Reboot Invariant**:
   If `state.snooze_until_ts and now_ts < state.snooze_until_ts`, `reboot_names_tick` MUST NOT include the miner under any condition.
2. **Alert Notification Invariant**:
   If a single-miner episode alert is triggered for a miner whose `snooze_until_ts > now_ts`, the notification MUST be suppressed.
3. **Persistent Reminder Invariant**:
   Persistent reminder alerts for snoozed miners MUST be suppressed.
