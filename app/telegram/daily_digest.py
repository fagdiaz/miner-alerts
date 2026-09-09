"""Daily Executive Digest generation and scheduling (Spec 034).

Aggregates 24-hour fleet telemetry from SQLite (uptime %, average TH/s,
J/TH efficiency, mining shares quality, operational incidents) and formats
a clean executive brief for scheduled morning dispatch and /digest on-demand.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ARGENTINA_TZ = datetime.timezone(datetime.timedelta(hours=-3))


def is_digest_due(
    now_dt: datetime.datetime,
    target_time_str: str = "08:00",
    last_sent_date: Optional[str] = None,
) -> bool:
    """Return True if local time is at or after target_time_str and not yet sent today."""
    today_str = now_dt.strftime("%Y-%m-%d")
    if last_sent_date == today_str:
        return False

    raw = (target_time_str or "08:00").strip()
    try:
        parts = raw.split(":")
        t_hour = int(parts[0])
        t_minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        t_hour, t_minute = 8, 0

    if now_dt.hour > t_hour:
        return True
    if now_dt.hour == t_hour and now_dt.minute >= t_minute:
        return True
    return False


def inspect_latest_backup(backup_root: Optional[Path | str] = None) -> Dict[str, Any]:
    """Inspect backup root directory and return latest verified backup metadata."""
    root = Path(backup_root) if backup_root else Path("backups")
    verified_dir = root / "verified"
    if not verified_dir.exists():
        return {"verified": False, "reason": "no_verified_dir"}

    candidates = [p for p in verified_dir.iterdir() if p.is_dir()]
    if not candidates:
        return {"verified": False, "reason": "no_backups"}

    # Candidate directory names start with ISO timestamp: YYYYMMDDTHHMMSSZ_...
    candidates.sort(key=lambda p: p.name, reverse=True)
    latest_dir = candidates[0]

    manifest_file = latest_dir / "manifest.json"
    db_file = latest_dir / "miner_alerts.db"

    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            size_bytes = data.get("file_size_bytes", 0)
            if not size_bytes and db_file.exists():
                size_bytes = db_file.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            start_iso = data.get("start_iso", "")
            # Format time
            time_str = "03:00"
            date_str = ""
            if start_iso:
                try:
                    dt = datetime.datetime.fromisoformat(start_iso)
                    if dt.tzinfo is not None:
                        dt_local = dt.astimezone(ARGENTINA_TZ)
                    else:
                        dt_local = dt
                    time_str = dt_local.strftime("%H:%M")
                    date_str = dt_local.strftime("%d/%m")
                except Exception:
                    time_str = "03:00"

            is_ok = data.get("integrity_check") == "ok"
            return {
                "verified": is_ok,
                "size_mb": size_mb,
                "time_str": time_str,
                "date_str": date_str,
                "backup_id": latest_dir.name,
            }
        except Exception:
            pass

    if db_file.exists():
        stat = db_file.stat()
        size_mb = stat.st_size / (1024 * 1024)
        dt = datetime.datetime.fromtimestamp(stat.st_mtime, tz=ARGENTINA_TZ)
        return {
            "verified": True,
            "size_mb": size_mb,
            "time_str": dt.strftime("%H:%M"),
            "date_str": dt.strftime("%d/%m"),
            "backup_id": latest_dir.name,
        }

    return {"verified": False, "reason": "empty_backup_dir"}


def fetch_daily_digest_metrics(
    db_path: Path | str,
    miners: List[Dict[str, Any]],
    now_ts: Optional[float] = None,
    backup_root: Optional[Path | str] = None,
    states: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Query SQLite database for 24h executive telemetry metrics."""
    curr_ts = now_ts if now_ts is not None else time.time()
    start_ts = curr_ts - 86400.0

    nominal_ths_total = sum(float(m.get("threshold_ths", 100.0)) for m in miners)
    total_miners_count = len(miners)

    res: Dict[str, Any] = {
        "window_start_ts": start_ts,
        "window_end_ts": curr_ts,
        "total_samples": 0,
        "fleet_uptime_pct": 100.0,
        "active_miners_count": total_miners_count,
        "total_miners_count": total_miners_count,
        "avg_hashrate_ths": 0.0,
        "nominal_hashrate_ths": nominal_ths_total,
        "avg_efficiency_j_th": None,
        "shares_accepted_pct": 100.0,
        "shares_rejected_pct": 0.0,
        "hw_errors_delta": 0,
        "incidents_24h": 0,
        "reboots_24h": 0,
        "backup_status": inspect_latest_backup(backup_root),
        "snoozed_miners": [],
    }

    # Identify currently snoozed miners
    if states:
        from app.telegram.snooze import is_miner_snoozed
        for m in miners:
            key = f"{m['name']}|{m['host']}:{m['port']}"
            st = states.get(key)
            if is_miner_snoozed(st, curr_ts):
                disp_n = m["name"].replace("S19JPRO-", "").replace("s19jpro-", "")
                res["snoozed_miners"].append(disp_n)

    db_p = Path(db_path)
    if not db_p.exists():
        return res

    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_p.resolve()}?mode=ro", uri=True, timeout=2.0)
        cursor = conn.cursor()

        # 1. Total samples & Uptime
        cursor.execute(
            """
            SELECT count(id),
                   count(CASE WHEN state = 'OK' OR (responded = 1 AND rate_ths >= threshold_ths) THEN 1 END)
            FROM telemetry_samples
            WHERE observed_ts >= ? AND observed_ts <= ?
            """,
            (start_ts, curr_ts),
        )
        row = cursor.fetchone()
        if row and row[0] > 0:
            res["total_samples"] = row[0]
            ok_samples = row[1]
            res["fleet_uptime_pct"] = (ok_samples / row[0]) * 100.0

        # 2. Average hashrate per miner in 24h
        cursor.execute(
            """
            SELECT miner_name, avg(rate_ths)
            FROM telemetry_samples
            WHERE observed_ts >= ? AND observed_ts <= ? AND rate_ths IS NOT NULL AND rate_ths > 0
            GROUP BY miner_name
            """,
            (start_ts, curr_ts),
        )
        miner_avgs = cursor.fetchall()
        if miner_avgs:
            res["avg_hashrate_ths"] = sum(row[1] for row in miner_avgs)
            res["active_miners_count"] = len(miner_avgs)

        # 3. Energy efficiency (J/TH = Watts / TH/s)
        cursor.execute(
            """
            SELECT avg(chain_power_w_total / rate_ths)
            FROM telemetry_samples
            WHERE observed_ts >= ? AND observed_ts <= ?
              AND rate_ths > 5.0
              AND chain_power_w_total > 500.0
            """,
            (start_ts, curr_ts),
        )
        eff_row = cursor.fetchone()
        if eff_row and eff_row[0] is not None:
            res["avg_efficiency_j_th"] = float(eff_row[0])

        # 4. Shares delta in 24h
        cursor.execute(
            """
            SELECT miner_name,
                   max(accepted_shares_total) - min(accepted_shares_total),
                   max(rejected_shares_total) - min(rejected_shares_total),
                   max(hw_errors_total) - min(hw_errors_total)
            FROM telemetry_samples
            WHERE observed_ts >= ? AND observed_ts <= ?
              AND accepted_shares_total IS NOT NULL
            GROUP BY miner_name
            """,
            (start_ts, curr_ts),
        )
        shares_rows = cursor.fetchall()
        total_acc = sum(max(0, r[1] or 0) for r in shares_rows)
        total_rej = sum(max(0, r[2] or 0) for r in shares_rows)
        total_hw = sum(max(0, r[3] or 0) for r in shares_rows)
        res["hw_errors_delta"] = total_hw

        if (total_acc + total_rej) > 0:
            res["shares_accepted_pct"] = (total_acc / (total_acc + total_rej)) * 100.0
            res["shares_rejected_pct"] = (total_rej / (total_acc + total_rej)) * 100.0

        # 5. Operational incidents in 24h (warning/critical events)
        cursor.execute(
            """
            SELECT count(id)
            FROM operational_events
            WHERE occurred_ts >= ? AND occurred_ts <= ?
              AND severity IN ('warning', 'critical')
            """,
            (start_ts, curr_ts),
        )
        inc_row = cursor.fetchone()
        if inc_row:
            res["incidents_24h"] = inc_row[0]

        # 6. Reboots executed in 24h
        cursor.execute(
            """
            SELECT count(id)
            FROM operational_events
            WHERE occurred_ts >= ? AND occurred_ts <= ?
              AND event_type IN ('reboot_action', 'reboot_execute')
            """,
            (start_ts, curr_ts),
        )
        rb_row = cursor.fetchone()
        reboots = rb_row[0] if rb_row else 0

        # Also check reboot_decisions if available
        cursor.execute(
            """
            SELECT count(id)
            FROM reboot_decisions
            WHERE evaluated_ts >= ? AND evaluated_ts <= ?
              AND result = 'executed'
            """,
            (start_ts, curr_ts),
        )
        dec_row = cursor.fetchone()
        if dec_row:
            reboots = max(reboots, dec_row[0])
        res["reboots_24h"] = reboots

    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return res


def format_daily_digest(metrics: Dict[str, Any], date_str: Optional[str] = None) -> str:
    """Format the aggregated metrics into a Telegram executive brief."""
    if not date_str:
        dt = datetime.datetime.now(ARGENTINA_TZ)
        date_str = dt.strftime("%d/%m/%Y")

    uptime_pct = metrics.get("fleet_uptime_pct", 100.0)
    active_m = metrics.get("active_miners_count", 0)
    total_m = metrics.get("total_miners_count", 0)

    avg_ths = metrics.get("avg_hashrate_ths", 0.0)
    nom_ths = metrics.get("nominal_hashrate_ths", 0.0)

    eff = metrics.get("avg_efficiency_j_th")
    if eff is not None and eff > 0:
        eff_str = f"{eff:.1f} J/TH"
    else:
        # Fallback estimation if watt data not reported by hardware
        eff_str = "N/D (sin telemetría de watts)"

    acc_pct = metrics.get("shares_accepted_pct", 100.0)
    rej_pct = metrics.get("shares_rejected_pct", 0.0)

    incidents = metrics.get("incidents_24h", 0)
    reboots = metrics.get("reboots_24h", 0)

    backup = metrics.get("backup_status", {})
    if backup.get("verified"):
        b_time = backup.get("time_str", "03:00")
        b_size = backup.get("size_mb", 0.0)
        backup_str = f"✅ Verificado ({b_size:.1f} MB a las {b_time})"
    else:
        backup_str = "⚠️ Sin backups recientes"

    snoozed = metrics.get("snoozed_miners", [])

    lines = [
        f"☀️ *Miner Alerts — Reporte Diario* ({date_str})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"• *Uptime Flota*: {uptime_pct:.1f}% ({active_m}/{total_m} mineros OK)",
        f"• *Hashrate Promedio*: {avg_ths:.1f} TH/s (Nominal: {nom_ths:.1f} TH/s)",
        f"• *Eficiencia Promedio*: {eff_str}",
        f"• *Shares*: {acc_pct:.2f}% aceptados ({rej_pct:.2f}% rechazos)",
        f"• *Eventos en 24h*: {incidents} anomalías, {reboots} reinicios",
        f"• *Backup SQLite*: {backup_str}",
    ]

    if snoozed:
        names_str = ", ".join(snoozed)
        lines.append(f"• *Mantenimiento*: 🔕 {len(snoozed)} silenciado(s) ({names_str})")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
