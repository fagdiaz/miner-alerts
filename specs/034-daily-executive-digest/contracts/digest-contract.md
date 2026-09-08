# Architecture & API Contract: Daily Executive Digest (Spec 034)

**Specification**: [spec.md](../spec.md)  
**Status**: ACTIVE  

---

## 1. Data Aggregation Contract (`app/daily_digest.py`)

### `fetch_daily_digest_metrics(db_path: Path | str, miners: list, now_ts: Optional[float] = None) -> Dict[str, Any]`

Input:
- `db_path`: Path to SQLite database (`miner_alerts.db`).
- `miners`: Configured miner list from `config.json`.
- `now_ts`: Current timestamp (defaults to `time.time()`).

Window: `[now_ts - 86400, now_ts]` (24 hours).

Returned Dictionary:
```python
{
    "window_start_ts": float,
    "window_end_ts": float,
    "total_samples": int,
    "fleet_uptime_pct": float,          # (ok_samples / total_samples) * 100
    "active_miners_count": int,         # Currently reporting OK or responsive
    "total_miners_count": int,          # len(miners)
    "avg_hashrate_ths": float,          # Sum of average TH/s per miner in window
    "nominal_hashrate_ths": float,      # Sum of configured threshold TH/s
    "avg_efficiency_j_th": Optional[float], # Watts / (TH/s) if power is available
    "accepted_shares": int,
    "rejected_shares": int,
    "shares_accepted_pct": float,       # accepted / (accepted + rejected) * 100
    "shares_rejected_pct": float,       # rejected / (accepted + rejected) * 100
    "hw_errors_delta": int,
    "incidents_24h": int,               # Warning/critical events in 24h
    "reboots_24h": int,                 # Reboot decisions/actions executed in 24h
    "backup_status": {
        "verified": bool,
        "backup_date_str": str,
        "backup_time_str": str,
        "size_mb": float,
    },
    "snoozed_miners_count": int,
}
```

---

## 2. Text Formatting Contract

### Template Output:
```text
☀️ Miner Alerts — Reporte Diario ({DD/MM/YYYY})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Uptime Flota: {uptime_pct:.1f}% ({active}/{total} mineros OK)
• Hashrate Promedio: {avg_ths:.1f} TH/s (Nominal: {nominal_ths:.1f} TH/s)
• Eficiencia Promedio: {efficiency_str}
• Shares: {accepted_pct:.2f}% aceptados ({rejected_pct:.2f}% rechazos)
• Eventos en 24h: {incidents} anomalías, {reboots} reinicios
• Backup SQLite: {backup_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If any miners are snoozed:
```text
• Mineros en Mantenimiento: {snoozed_count} ({snoozed_names})
```

---

## 3. Scheduling & State Contract

### State (`app/state.json`)
```json
{
  "last_daily_digest_date": "2026-09-08",
  ...
}
```

### Scheduling Logic:
```python
def is_digest_due(
    now_dt: datetime,
    target_time_str: str,
    last_sent_date: Optional[str],
) -> bool:
    """Return True if local time is at or after target_time and not sent today."""
    today_str = now_dt.strftime("%Y-%m-%d")
    if last_sent_date == today_str:
        return False
    try:
        t_hour, t_minute = map(int, target_time_str.strip().split(":"))
    except ValueError:
        t_hour, t_minute = 8, 0
    return now_dt.hour > t_hour or (now_dt.hour == t_hour and now_dt.minute >= t_minute)
```
