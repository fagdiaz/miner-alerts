"""Telegram visual charts generator for Miner Alerts (Spec 032).

Extracts time-series telemetry from SQLite and renders high-contrast,
dark-themed PNG charts directly into memory (BytesIO) without filesystem artifacts.
"""

from __future__ import annotations

import datetime
import io
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DARK_BG = "#181c20"
TEXT_COLOR = "#f3f4f6"
GRID_COLOR = "#2d343c"
COLOR_PALETTE = ["#10b981", "#3b82f6", "#a855f7", "#f59e0b", "#ec4899", "#06b6d4"]


def _connect_ro(db_path: Path | str) -> sqlite3.Connection:
    # mode=ro timeout=2.0 via create_readonly_connection
    p = Path(db_path).expanduser()
    if not p.is_absolute() and not p.exists():
        repo_root = Path(__file__).resolve().parent.parent.parent
        if (repo_root / p).exists():
            p = repo_root / p
    resolved = p.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Database not found: {resolved}")
    from app.core.event_store import create_readonly_connection
    return create_readonly_connection(resolved, timeout=3.0)


def fetch_miner_chart_data(
    db_path: Path | str,
    miner_id: str,
    hours: float = 1.0,
    now_ts: Optional[float] = None,
    max_points: int = 150,
) -> Dict[str, Any]:
    """Query telemetry samples for a single miner over the requested window."""
    now = now_ts or time.time()
    since_ts = now - (hours * 3600.0)

    miner_clean = miner_id.split("-")[-1].strip()
    miner_full = f"S19JPRO-{miner_clean}" if not miner_id.startswith("S19JPRO-") else miner_id

    conn = _connect_ro(db_path)
    try:
        from app.core.event_store import execute_readonly_with_retry
        rows = execute_readonly_with_retry(
            conn,
            """
            SELECT observed_ts, rate_ths, threshold_ths, max_temp_c, fan_rpm_max, state
            FROM telemetry_samples
            WHERE (miner_name = ? OR miner_name = ? OR miner_key LIKE ?)
              AND observed_ts >= ?
            ORDER BY observed_ts ASC
            """,
            (miner_id, miner_full, f"%{miner_clean}%", since_ts),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "miner_name": miner_full,
            "miner_id": miner_clean,
            "threshold_ths": 60.0,
            "timestamps": [],
            "rates": [],
            "temps": [],
            "fans": [],
            "avg_rate": 0.0,
            "max_temp": 0.0,
            "count": 0,
        }

    # Downsample if count > max_points
    step = max(1, len(rows) // max_points)
    sampled = rows[::step]

    timestamps = [float(r["observed_ts"]) for r in sampled]
    rates = [float(r["rate_ths"]) if r["rate_ths"] is not None else 0.0 for r in sampled]
    temps = [float(r["max_temp_c"]) if r["max_temp_c"] is not None else 0.0 for r in sampled]
    fans = [float(r["fan_rpm_max"]) if r["fan_rpm_max"] is not None else 0.0 for r in sampled]
    threshold_ths = float(sampled[-1]["threshold_ths"] or 60.0)

    valid_rates = [r for r in rates if r > 0]
    avg_rate = sum(valid_rates) / len(valid_rates) if valid_rates else 0.0
    max_temp = max(temps) if temps else 0.0

    return {
        "miner_name": miner_full,
        "miner_id": miner_clean,
        "threshold_ths": threshold_ths,
        "timestamps": timestamps,
        "rates": rates,
        "temps": temps,
        "fans": fans,
        "avg_rate": avg_rate,
        "max_temp": max_temp,
        "count": len(timestamps),
    }


def fetch_fleet_chart_data(
    db_path: Path | str,
    configured_miners: List[Dict[str, Any]],
    hours: float = 1.0,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """Query telemetry samples for all configured miners."""
    now = now_ts or time.time()
    series: List[Dict[str, Any]] = []

    for m in configured_miners:
        m_name = m.get("name", "")
        data = fetch_miner_chart_data(db_path, m_name, hours=hours, now_ts=now)
        if data["count"] > 0:
            series.append(data)

    return {
        "hours": hours,
        "series": series,
        "count": len(series),
    }


def fetch_group_chart_data(
    db_path: Path | str,
    group_name: str,
    configured_miners: List[Dict[str, Any]],
    hours: float = 1.0,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """Query telemetry samples for all configured miners belonging to an electrical group."""
    now = now_ts or time.time()
    target_grp = group_name.strip().lower()
    matched_miners: List[Dict[str, Any]] = []

    for m in configured_miners:
        grp = (m.get("electrical_group") or m.get("group") or "").strip().lower()
        if grp == target_grp or (target_grp and target_grp in grp) or (grp and grp in target_grp):
            matched_miners.append(m)

    series: List[Dict[str, Any]] = []
    for m in matched_miners:
        m_name = m.get("name", "")
        data = fetch_miner_chart_data(db_path, m_name, hours=hours, now_ts=now)
        if data["count"] > 0:
            series.append(data)

    return {
        "group_name": group_name,
        "hours": hours,
        "series": series,
        "count": len(series),
        "total_miners": len(matched_miners),
    }


def render_miner_chart_png(data: Dict[str, Any], hours: float = 1.0) -> bytes:
    """Render a dual-subplot PNG chart (Hashrate + Temp/Fans) in memory."""
    if data["count"] == 0:
        raise ValueError(f"No hay muestras de telemetría disponibles para el minero {data['miner_name']}.")

    dates = [datetime.datetime.fromtimestamp(ts) for ts in data["timestamps"]]

    fig, (ax_rate, ax_aux) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]}, dpi=100
    )
    try:
        # Style dark background
        fig.patch.set_facecolor(DARK_BG)
        for ax in (ax_rate, ax_aux):
            ax.set_facecolor(DARK_BG)
            ax.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.7)
            ax.tick_params(colors=TEXT_COLOR, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color("#374151")

        # --- Top Subplot: Hashrate vs Threshold ---
        m_name = data["miner_name"]
        avg_str = f"{data['avg_rate']:.1f} TH/s"
        curr_str = f"{data['rates'][-1]:.1f} TH/s"
        ax_rate.set_title(
            f"Miner Alerts — {m_name} ({hours:.0f}h) | Actual: {curr_str} | Promedio: {avg_str}",
            color=TEXT_COLOR,
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax_rate.plot(dates, data["rates"], color="#10b981", linewidth=2.2, label=f"Hashrate ({curr_str})")
        ax_rate.fill_between(dates, data["rates"], color="#10b981", alpha=0.15)
        ax_rate.axhline(
            data["threshold_ths"],
            color="#f59e0b",
            linestyle="--",
            linewidth=1.5,
            label=f"Umbral ({data['threshold_ths']:.0f} TH/s)",
        )
        ax_rate.set_ylabel("Hashrate (TH/s)", color=TEXT_COLOR, fontsize=10)
        ax_rate.legend(loc="upper left", facecolor="#1f2937", edgecolor="#374151", labelcolor=TEXT_COLOR)

        # --- Bottom Subplot: Temperature & Fans ---
        ax_aux.plot(dates, data["temps"], color="#ef4444", linewidth=1.8, label=f"Temp Max ({data['max_temp']:.0f}°C)")
        ax_aux.set_ylabel("Temp (°C)", color="#ef4444", fontsize=10)
        ax_aux.tick_params(axis="y", labelcolor="#ef4444")

        # Secondary axis for Fan RPM if data exists
        if any(f > 0 for f in data["fans"]):
            ax_fan = ax_aux.twinx()
            ax_fan.plot(dates, data["fans"], color="#3b82f6", linestyle=":", linewidth=1.4, label="Fan RPM")
            ax_fan.set_ylabel("Fan RPM", color="#3b82f6", fontsize=10)
            ax_fan.tick_params(axis="y", labelcolor="#3b82f6", labelsize=9)
            for spine in ax_fan.spines.values():
                spine.set_color("#374151")

        # Format X-axis date format
        if hours <= 3:
            ax_aux.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        elif hours <= 24:
            ax_aux.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%d/%m"))
        else:
            ax_aux.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

        fig.autofmt_xdate(rotation=0, ha="center")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=DARK_BG, edgecolor="none")
        buf.seek(0)
        return buf.getvalue()
    finally:
        plt.close(fig)


def render_fleet_chart_png(fleet_data: Dict[str, Any], hours: float = 1.0) -> bytes:
    """Render a multi-series comparison chart for all miners in memory."""
    if fleet_data["count"] == 0:
        raise ValueError("No hay datos de telemetría disponibles para la flota.")

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=100)
    try:
        fig.patch.set_facecolor(DARK_BG)
        ax.set_facecolor(DARK_BG)
        ax.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.7)
        ax.tick_params(colors=TEXT_COLOR, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#374151")

        for idx, s in enumerate(fleet_data["series"]):
            color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]
            dates = [datetime.datetime.fromtimestamp(ts) for ts in s["timestamps"]]
            rates = s["rates"]
            curr_str = f"{rates[-1]:.1f} TH/s" if rates else "-"
            ax.plot(dates, rates, color=color, linewidth=1.8, label=f"{s['miner_id']}: {curr_str}")

        ax.set_title(
            f"Miner Alerts — Rendimiento de Flota ({hours:.0f}h)",
            color=TEXT_COLOR,
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_ylabel("Hashrate (TH/s)", color=TEXT_COLOR, fontsize=10)
        ax.legend(loc="upper left", facecolor="#1f2937", edgecolor="#374151", labelcolor=TEXT_COLOR)

        if hours <= 3:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%d/%m"))

        fig.autofmt_xdate(rotation=0, ha="center")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=DARK_BG, edgecolor="none")
        buf.seek(0)
        return buf.getvalue()
    finally:
        plt.close(fig)


CHART_RANGES: List[Tuple[int, str]] = [
    (1, "1h"),
    (6, "6h"),
    (24, "24h"),
    (168, "7d"),
]


def build_chart_range_keyboard(target: str, current_hours: float = 1.0) -> Dict[str, Any]:
    """Build an inline keyboard with time-range buttons (1h, 6h, 24h, 7d).

    The active range is decorated with bullet indicators (e.g. • 1h •).
    """
    buttons = []
    clean_target = target.strip()
    if clean_target.startswith("S19JPRO-"):
        clean_target = clean_target.replace("S19JPRO-", "")

    for r_hours, label in CHART_RANGES:
        is_active = abs(current_hours - r_hours) < 0.2
        btn_text = f"• {label} •" if is_active else label
        cb_data = f"chart_range:{clean_target}:{r_hours}"
        buttons.append({"text": btn_text, "callback_data": cb_data})

    return {
        "inline_keyboard": [buttons]
    }


def render_group_chart_png(group_data: Dict[str, Any], hours: float = 1.0) -> bytes:
    """Render a dual-subplot PNG chart (Hashrate on top, Max Chip Temp on bottom) for a group."""
    if group_data.get("count", 0) == 0:
        grp_name = group_data.get("group_name", "desconocido")
        raise ValueError(f"No hay muestras de telemetría disponibles para el grupo {grp_name}.")

    fig, (ax_rate, ax_temp) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]}, dpi=100
    )
    try:
        fig.patch.set_facecolor(DARK_BG)
        for ax in (ax_rate, ax_temp):
            ax.set_facecolor(DARK_BG)
            ax.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.7)
            ax.tick_params(colors=TEXT_COLOR, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color("#374151")

        grp_label = group_data.get("group_name", "Grupo").upper()
        ax_rate.set_title(
            f"Miner Alerts — Grupo: {grp_label} ({hours:.0f}h) | {group_data['count']} mineros",
            color=TEXT_COLOR,
            fontsize=12,
            fontweight="bold",
            pad=12,
        )

        threshold_drawn = False
        for idx, s in enumerate(group_data["series"]):
            color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]
            dates = [datetime.datetime.fromtimestamp(ts) for ts in s["timestamps"]]
            rates = s["rates"]
            temps = s["temps"]
            curr_rate_str = f"{rates[-1]:.1f} TH/s" if rates else "-"
            curr_temp_str = f"{temps[-1]:.0f}°C" if temps else "-"

            # Top: Hashrate
            ax_rate.plot(
                dates,
                rates,
                color=color,
                linewidth=1.8,
                label=f"{s['miner_id']}: {curr_rate_str}",
            )

            # Threshold line
            if not threshold_drawn and s.get("threshold_ths"):
                ax_rate.axhline(
                    s["threshold_ths"],
                    color="#f59e0b",
                    linestyle="--",
                    linewidth=1.2,
                    alpha=0.8,
                    label=f"Umbral ({s['threshold_ths']:.0f} TH/s)",
                )
                threshold_drawn = True

            # Bottom: Temperature
            ax_temp.plot(
                dates,
                temps,
                color=color,
                linewidth=1.6,
                label=f"{s['miner_id']}: {curr_temp_str}",
            )

        ax_rate.set_ylabel("Hashrate (TH/s)", color=TEXT_COLOR, fontsize=10)
        ax_rate.legend(loc="upper left", facecolor="#1f2937", edgecolor="#374151", labelcolor=TEXT_COLOR, fontsize=8)

        ax_temp.set_ylabel("Temp Chip (°C)", color=TEXT_COLOR, fontsize=10)
        ax_temp.legend(loc="upper left", facecolor="#1f2937", edgecolor="#374151", labelcolor=TEXT_COLOR, fontsize=8)

        if hours <= 3:
            ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        elif hours <= 24:
            ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%d/%m"))
        else:
            ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))

        fig.autofmt_xdate(rotation=0, ha="center")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=DARK_BG, edgecolor="none")
        buf.seek(0)
        return buf.getvalue()
    finally:
        plt.close(fig)
