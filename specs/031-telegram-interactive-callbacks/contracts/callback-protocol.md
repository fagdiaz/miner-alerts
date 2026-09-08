# Contract: Telegram Callback Protocol & Inline Keyboards (Spec 031)

**Status**: Definitive Contract  
**Target API**: Telegram Bot API 5.0+ (`getUpdates`, `sendMessage`, `answerCallbackQuery`, `editMessageReplyMarkup`)  
**Hard Limit**: Telegram Bot API strictly limits `callback_data` strings to **64 UTF-8 bytes**.

---

## 1. Action Grammar & Payload Budget

Every interactive button MUST encode a compact, deterministic string strictly under 32 bytes:

| Action Intent | `callback_data` Pattern | Example | Byte Size | Action Executed |
|---|---|---|---|---|
| **Run Diagnostic** | `diag:<miner_id>` | `diag:23` | 7 bytes | Dispatches `/diagnose <miner>` to chat. |
| **Request Graph** | `chart:<miner_id>` | `chart:23` | 8 bytes | Dispatches `/chart <miner>` to chat. |
| **Request Silence** | `snz:<miner_id>:<min>` | `snz:23:60` | 9 bytes | Dispatches `/snooze <miner> <min>`. |
| **Initiate Reboot** | `rb_req:<miner_id>` | `rb_req:23` | 9 bytes | Transitions message to confirmation keyboard. |
| **Confirm Reboot** | `rb_cfm:<tok>:<miner_id>`| `rb_cfm:e8f2a1:23` | 17 bytes | Executes guarded reboot authorization flow. |
| **Cancel Reboot** | `rb_ccl:<miner_id>` | `rb_ccl:23` | 9 bytes | Restores original alert keyboard. |
| **No-Operation** | `noop` | `noop` | 4 bytes | Static informative button (e.g. "Reinicio Solicitado"). |

---

## 2. Keyboard Layouts

### Layout A: Alert Episode Action Bar
Attached to episode notifications and incident alerts:
```json
{
  "inline_keyboard": [
    [
      { "text": "🩺 Diagnosticar", "callback_data": "diag:23" },
      { "text": "📊 Ver Gráfico", "callback_data": "chart:23" }
    ],
    [
      { "text": "🔄 Reiniciar Minero 23", "callback_data": "rb_req:23" },
      { "text": "🔕 Silenciar 1h", "callback_data": "snz:23:60" }
    ]
  ]
}
```

### Layout B: Interactive 2-Step Confirmation
Generated in-place via `editMessageReplyMarkup` when `rb_req:<miner>` is received:
```json
{
  "inline_keyboard": [
    [
      { "text": "⚠️ CONFIRMAR REINICIO 23", "callback_data": "rb_cfm:e8f2a1:23" }
    ],
    [
      { "text": "❌ Cancelar", "callback_data": "rb_ccl:23" }
    ]
  ]
}
```

### Layout C: Settled Action
Replaces confirmation buttons once action is taken:
```json
{
  "inline_keyboard": [
    [
      { "text": "✅ Reinicio Iniciado (Enfriamiento 15m)", "callback_data": "noop" }
    ]
  ]
}
```

---

## 3. Security & Concurrency Invariants

1. **Strict User Authentication**:
   - `callback_query.from.id` MUST match `int(config["telegram"]["chat_id"])`.
   - If unauthorized, call `answerCallbackQuery(text="⛔ No autorizado", show_alert=True)` and drop immediately.
2. **Immediate Acknowledgment**:
   - Every callback MUST invoke `answerCallbackQuery` within 1.0s.
   - For `diag`, show toast: `"Ejecutando diagnóstico..."`.
   - For `rb_req`, show toast: `"Confirmación requerida (expira en 60s)"`.
3. **Confirmation Token Lifecycle**:
   - Tokens are 6-character hex strings generated via `secrets.token_hex(3)`.
   - Active tokens expire after 60.0 seconds.
   - If an expired token is tapped: `answerCallbackQuery(text="⏱️ Token expirado. Reintente.", show_alert=True)`.
   - Memory bounded: max 10 active tokens in registry; auto-pruned on every tick.
