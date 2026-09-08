# Contract: Telegram Visual Charts Engine (Spec 032)

**Status**: Definitive Contract  
**Target Output**: PNG image stream (`image/png`) delivered via Telegram `sendPhoto`.  
**Hard Constraints**:
- Pure in-memory streaming: `io.BytesIO`.
- Read-only SQLite access: `file:...mode=ro`.
- Render duration: < 1.5 seconds.
- Payload resolution: 1000 x 550 px (optimized for mobile Telegram preview).

---

## 1. Visual Specification & Theme

The chart uses a high-contrast dark theme optimized for mobile OLED screens and readability:

| Element | Color Code | Style | Purpose |
|---|---|---|---|
| **Background** | `#181c20` | Solid | Dark slate background. |
| **Grid Lines** | `#2d343c` | Dotted | Subtle time and value guide. |
| **Hashrate Line** | `#10b981` (Emerald) | 2.5px solid | Main hashrate progression (TH/s). |
| **Threshold Line** | `#f59e0b` (Amber) | 1.5px dashed | Nominal minimum threshold. |
| **Max Temp Line** | `#ef4444` (Crimson) | 2.0px solid | Board temperature (°C) on secondary axis. |
| **Fan RPM Line** | `#3b82f6` (Blue) | 1.0px dotted | Fan speed progression (optional overlay). |
| **Text / Labels** | `#f3f4f6` (Off-white) | Sans-serif | Axes, titles, timestamps. |

---

## 2. Telegram `sendPhoto` HTTP Contract

```http
POST https://api.telegram.org/bot<TOKEN>/sendPhoto
Content-Type: multipart/form-data

chat_id: 1206728163
caption: 📊 S19JPRO-23 — Últimas 24 horas (Promedio: 98.9 TH/s | Max Temp: 78°C)
photo: [Binary PNG stream]
```

### Response Handling
- **HTTP 200**: Success.
- **HTTP 400/429/500**: Caught cleanly, logged as `TG_PHOTO_ERR`, fallback to text summary without crashing the caller.

---

## 3. Query Performance & Aggregation

To avoid plotting 50,000 individual data points across a 24-hour window:
- Window ≤ 2 hours: raw samples plotted directly.
- Window > 2 hours: downsampled using SQLite time bucketing (e.g. `CAST(observed_ts / 300 AS INT)` for 5-minute averages).
- Query execution bounded to < 100 ms.
