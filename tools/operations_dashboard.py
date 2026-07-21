#!/usr/bin/env python3
"""Generate a self-contained read-only operations dashboard from SQLite."""

from __future__ import annotations

import argparse
import html
import math
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.mining_quality import analyze_mining_quality
from app.stability_profile import analyze_stability


_KNOWN_TABLES = frozenset(
    ("telemetry_samples", "operational_events", "reboot_decisions", "firmware_events")
)


def open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    if table_name not in _KNOWN_TABLES:
        return False
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _natural_key(value: Any) -> tuple[Any, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", normalized))


def _latest_samples(connection: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(connection, "telemetry_samples"):
        return []
    rows = connection.execute(
        """
        SELECT sample.*
        FROM telemetry_samples AS sample
        WHERE sample.id = (
            SELECT candidate.id
            FROM telemetry_samples AS candidate
            WHERE candidate.miner_key = sample.miner_key
            ORDER BY candidate.observed_ts DESC, candidate.id DESC
            LIMIT 1
        )
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def _window_rows(
    connection: sqlite3.Connection,
    table_name: str,
    timestamp_column: str,
    *,
    since_ts: float,
    limit: int,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    if table_name not in _KNOWN_TABLES or not _table_exists(connection, table_name):
        return []
    direction = "ASC" if ascending else "DESC"
    rows = connection.execute(
        f"""
        SELECT * FROM {table_name}
        WHERE {timestamp_column} >= ?
        ORDER BY {timestamp_column} {direction}, id {direction}
        LIMIT ?
        """,
        (float(since_ts), int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def build_dashboard_data(
    connection: sqlite3.Connection,
    *,
    hours: float = 24.0,
    now_ts: Optional[float] = None,
    stale_after_seconds: float = 900.0,
    row_limit: int = 5_000,
    min_stability_samples: int = 12,
    min_quality_intervals: int = 3,
) -> dict[str, Any]:
    effective_now = time.time() if now_ts is None else float(now_ts)
    safe_hours = max(0.1, min(float(hours), 24.0 * 365.0))
    safe_stale_after = max(30.0, float(stale_after_seconds))
    safe_limit = max(10, min(int(row_limit), 50_000))
    since_ts = effective_now - safe_hours * 3600.0

    latest_samples = _latest_samples(connection, safe_limit)
    trend_rows = _window_rows(
        connection,
        "telemetry_samples",
        "observed_ts",
        since_ts=since_ts,
        limit=safe_limit,
        ascending=False,
    )
    events = _window_rows(
        connection,
        "operational_events",
        "occurred_ts",
        since_ts=since_ts,
        limit=min(safe_limit, 500),
    )
    decisions = _window_rows(
        connection,
        "reboot_decisions",
        "evaluated_ts",
        since_ts=since_ts,
        limit=min(safe_limit, 500),
    )
    firmware_events = _window_rows(
        connection,
        "firmware_events",
        "collected_ts",
        since_ts=since_ts,
        limit=min(safe_limit, 500),
    )

    histories: dict[str, list[float]] = defaultdict(list)
    sample_histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trend_rows:
        miner_key = str(row.get("miner_key") or "")
        if miner_key:
            sample_histories[miner_key].append(row)
    for row in reversed(trend_rows):
        rate = _finite(row.get("rate_ths"))
        miner_key = str(row.get("miner_key") or "")
        if miner_key and rate is not None:
            histories[miner_key].append(rate)

    latest_decisions: dict[str, str] = {}
    for row in decisions:
        miner_key = str(row.get("miner_key") or "")
        if miner_key and miner_key not in latest_decisions:
            latest_decisions[miner_key] = str(row.get("result") or "unknown")

    miners: list[dict[str, Any]] = []
    for sample in latest_samples:
        observed_ts = _finite(sample.get("observed_ts"))
        age_seconds = None if observed_ts is None else max(0.0, effective_now - observed_ts)
        stale = age_seconds is None or age_seconds > safe_stale_after
        miner_key = str(sample.get("miner_key") or "")
        stored_state = str(sample.get("state") or "UNKNOWN").upper()
        display_state = "STALE" if stale else stored_state
        sample_id = sample.get("id")
        prior_rows = [
            row
            for row in sample_histories.get(miner_key, [])
            if sample_id is None or row.get("id") != sample_id
        ]
        stability = analyze_stability(
            [sample, *prior_rows],
            now_ts=effective_now,
            stale_after_seconds=safe_stale_after,
            min_samples=min_stability_samples,
        )
        quality = analyze_mining_quality(
            [sample, *prior_rows],
            min_intervals=min_quality_intervals,
        )
        miners.append(
            {
                "miner_key": miner_key,
                "miner_name": str(sample.get("miner_name") or miner_key or "unknown"),
                "host": str(sample.get("host") or ""),
                "state": stored_state,
                "display_state": display_state,
                "responded": bool(sample.get("responded")),
                "rate_ths": _finite(sample.get("rate_ths")),
                "threshold_ths": _finite(sample.get("threshold_ths")),
                "active_boards": sample.get("active_boards"),
                "expected_boards": sample.get("expected_boards"),
                "max_temp_c": _finite(sample.get("max_temp_c")),
                "chain_voltage_mv_avg": _finite(sample.get("chain_voltage_mv_avg")),
                "chain_power_w_total": _finite(sample.get("chain_power_w_total")),
                "frequency_mhz_avg": _finite(sample.get("frequency_mhz_avg")),
                "hw_errors_total": sample.get("hw_errors_total"),
                "observed_ts": observed_ts,
                "age_seconds": age_seconds,
                "stale": stale,
                "rate_history": histories.get(miner_key, [])[-288:],
                "latest_decision": latest_decisions.get(miner_key),
                "stability": stability.as_dict(),
                "quality": quality.as_dict(),
            }
        )
    miners.sort(key=lambda item: _natural_key(item["miner_name"]))

    healthy = sum(
        1 for miner in miners if not miner["stale"] and miner["state"] == "OK"
    )
    stale_count = sum(1 for miner in miners if miner["stale"])
    state_counts = Counter(str(miner["display_state"]) for miner in miners)
    decision_counts = Counter(str(row.get("result") or "unknown") for row in decisions)
    event_counts = Counter(str(row.get("event_type") or "event") for row in events)
    stability_counts = Counter(
        str(miner["stability"]["status"]) for miner in miners
    )
    quality_counts = Counter(str(miner["quality"]["status"]) for miner in miners)

    return {
        "generated_ts": effective_now,
        "since_ts": since_ts,
        "hours": safe_hours,
        "stale_after_seconds": safe_stale_after,
        "row_limit": safe_limit,
        "summary": {
            "miners": len(miners),
            "healthy": healthy,
            "degraded": len(miners) - healthy,
            "stale": stale_count,
            "events": len(events),
            "decisions": len(decisions),
            "firmware_events": len(firmware_events),
        },
        "state_counts": dict(sorted(state_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "decision_counts": dict(sorted(decision_counts.items())),
        "stability_counts": dict(sorted(stability_counts.items())),
        "quality_counts": dict(sorted(quality_counts.items())),
        "miners": miners,
        "events": events[:50],
        "decisions": decisions[:50],
        "firmware_events": firmware_events[:50],
    }


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "N/A"), quote=True)


def _number(value: Any, digits: int = 1, suffix: str = "") -> str:
    numeric = _finite(value)
    return "N/A" if numeric is None else f"{numeric:.{digits}f}{suffix}"


def _timestamp(value: Any) -> str:
    numeric = _finite(value)
    if numeric is None:
        return "N/A"
    return datetime.fromtimestamp(numeric).strftime("%d/%m/%Y %H:%M:%S")


def _age(value: Any) -> str:
    numeric = _finite(value)
    if numeric is None:
        return "sin muestra"
    seconds = int(max(0.0, numeric))
    if seconds < 60:
        return f"hace {seconds}s"
    if seconds < 3_600:
        return f"hace {seconds // 60}m"
    if seconds < 86_400:
        return f"hace {seconds // 3_600}h"
    return f"hace {seconds // 86_400}d"


def _sparkline(values: list[float], threshold: Optional[float]) -> str:
    safe_values = [value for value in (_finite(item) for item in values) if value is not None]
    if not safe_values:
        return '<div class="spark-empty">Sin tendencia en la ventana</div>'
    width = 260.0
    height = 64.0
    floor_candidates = [*safe_values]
    ceiling_candidates = [*safe_values]
    safe_threshold = _finite(threshold)
    if safe_threshold is not None:
        floor_candidates.append(safe_threshold)
        ceiling_candidates.append(safe_threshold)
    low = min(floor_candidates)
    high = max(ceiling_candidates)
    span = max(1.0, high - low)
    count = len(safe_values)
    points: list[str] = []
    for index, value in enumerate(safe_values):
        x = 0.0 if count == 1 else index * width / (count - 1)
        y = height - ((value - low) / span * (height - 8.0)) - 4.0
        points.append(f"{x:.1f},{y:.1f}")
    threshold_line = ""
    if safe_threshold is not None:
        threshold_y = height - ((safe_threshold - low) / span * (height - 8.0)) - 4.0
        threshold_line = (
            f'<line x1="0" y1="{threshold_y:.1f}" x2="{width:.1f}" '
            f'y2="{threshold_y:.1f}" class="threshold-line" />'
        )
    return (
        f'<svg class="spark" viewBox="0 0 {width:.0f} {height:.0f}" '
        'role="img" aria-label="Tendencia de hashrate">'
        f'{threshold_line}<polyline points="{" ".join(points)}" /></svg>'
    )


def _state_class(state: str) -> str:
    normalized = state.lower()
    return normalized if normalized in ("ok", "low", "offline", "hashboard", "stale") else "unknown"


def _render_miner_card(miner: dict[str, Any]) -> str:
    state = str(miner["display_state"])
    board_value = miner.get("active_boards")
    board_expected = miner.get("expected_boards")
    boards = (
        f"{_esc(board_value)}/{_esc(board_expected)}"
        if board_value is not None or board_expected is not None
        else "N/A"
    )
    decision = miner.get("latest_decision") or "sin decision reciente"
    stability = miner.get("stability") or {}
    stability_status = str(stability.get("status") or "learning")
    stability_label = stability_status.upper()
    if stability_status == "learning":
        stability_label = "LEARNING {}/{}".format(
            int(stability.get("sample_count") or 0),
            int(stability.get("required_samples") or 0),
        )
    reason_items = list(stability.get("reasons") or [])[:3]
    reasons_html = (
        "".join(
            f"<li>{_esc(reason.get('message') or reason.get('code') or 'evidencia')}</li>"
            for reason in reason_items
        )
        if reason_items
        else "<li>Sin desvios relevantes frente al baseline.</li>"
    )
    rate_band = (stability.get("bands") or {}).get("rate_ths") or {}
    baseline_html = ""
    if rate_band and int(stability.get("sample_count") or 0) >= int(
        stability.get("required_samples") or 0
    ):
        baseline_html = (
            f'<p class="baseline">Base hash: {_number(rate_band.get("lower"), 1)}-'
            f'{_number(rate_band.get("upper"), 1)} TH/s</p>'
        )
    quality = miner.get("quality") or {}
    quality_status = str(quality.get("status") or "learning")
    quality_label = quality_status.upper()
    if quality_status == "learning":
        quality_label = "LEARNING {}/{}".format(
            int(quality.get("comparable_intervals") or 0),
            int(quality.get("required_intervals") or 0),
        )
    quality_reasons = list(quality.get("reasons") or [])[:3]
    quality_reasons_html = (
        "".join(
            f"<li>{_esc(reason.get('message') or reason.get('code') or 'evidencia')}</li>"
            for reason in quality_reasons
        )
        if quality_reasons
        else "<li>Sin degradacion de calidad en el ultimo intervalo.</li>"
    )
    quality_delta = quality.get("delta") or {}
    quality_interval = _number(quality_delta.get("interval_seconds"), 0, "s")
    quality_delta_html = (
        "<p class=\"baseline\">Intervalo {interval}: accepted {accepted}, "
        "rejected {rejected}, stale {stale}</p>"
    ).format(
        interval=_esc(quality_interval),
        accepted=_esc(quality_delta.get("accepted")),
        rejected=_esc(quality_delta.get("rejected")),
        stale=_esc(quality_delta.get("stale")),
    )
    return f"""
      <article class="miner-card state-{_state_class(state)}">
        <div class="miner-head">
          <div>
            <p class="eyebrow">{_esc(miner.get('host') or 'host N/A')}</p>
            <h3>{_esc(miner['miner_name'])}</h3>
          </div>
          <span class="state-pill">{_esc(state)}</span>
        </div>
        <div class="primary-rate">{_number(miner.get('rate_ths'), 2)} <small>TH/s</small></div>
        <p class="freshness">{_esc(_age(miner.get('age_seconds')))}</p>
        <div class="metrics">
          <div><span>Boards</span><strong>{boards}</strong></div>
          <div><span>Temp max</span><strong>{_number(miner.get('max_temp_c'), 1, ' C')}</strong></div>
          <div><span>Potencia cadena</span><strong>{_number(miner.get('chain_power_w_total'), 0, ' W')}</strong></div>
        </div>
        <div class="stability stability-{_esc(stability_status)}">
          <div><span>Stability Advisor</span><strong>{_esc(stability_label)}</strong></div>
          {baseline_html}
          <ul>{reasons_html}</ul>
        </div>
        <div class="quality quality-{_esc(quality_status)}">
          <div><span>Mining Quality</span><strong>{_esc(quality_label)}</strong></div>
          {quality_delta_html}
          <ul>{quality_reasons_html}</ul>
        </div>
        {_sparkline(miner.get('rate_history') or [], miner.get('threshold_ths'))}
        <div class="decision"><span>Ultima decision</span><strong>{_esc(decision)}</strong></div>
      </article>
    """


def _render_event_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="5" class="empty-cell">Sin eventos en la ventana</td></tr>'
    rows = []
    for event in events:
        rows.append(
            "<tr>"
            f"<td>{_esc(_timestamp(event.get('occurred_ts')))}</td>"
            f"<td>{_esc(event.get('miner_name') or 'sistema')}</td>"
            f"<td><span class=\"severity severity-{_state_class(str(event.get('severity') or 'unknown'))}\">{_esc(event.get('severity') or 'N/A')}</span></td>"
            f"<td>{_esc(event.get('event_type') or 'event')}</td>"
            f"<td>{_esc(event.get('summary') or '')}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_decision_rows(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return '<tr><td colspan="5" class="empty-cell">Sin decisiones en la ventana</td></tr>'
    rows = []
    for decision in decisions:
        result = str(decision.get("result") or "unknown")
        rows.append(
            "<tr>"
            f"<td>{_esc(_timestamp(decision.get('evaluated_ts')))}</td>"
            f"<td>{_esc(decision.get('miner_name') or decision.get('miner_key'))}</td>"
            f"<td><span class=\"decision-tag decision-{_state_class(result)}\">{_esc(result)}</span></td>"
            f"<td>{_number(decision.get('rate_ths'), 2, ' TH/s')}</td>"
            f"<td>{_number(decision.get('max_temp_c'), 1, ' C')}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_firmware_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="6" class="empty-cell">Sin eventos Vnish en la ventana</td></tr>'
    rows = []
    for event in events:
        rows.append(
            "<tr>"
            f"<td>{_esc(event.get('source_ts_text') or _timestamp(event.get('collected_ts')))}</td>"
            f"<td>{_esc(event.get('miner_name') or event.get('miner_key'))}</td>"
            f"<td><span class=\"severity severity-{_state_class(str(event.get('severity') or 'unknown'))}\">{_esc(event.get('severity') or 'N/A')}</span></td>"
            f"<td>{_esc(event.get('category') or 'firmware')}</td>"
            f"<td>{_esc(event.get('code') or 'firmware_event')}</td>"
            f"<td>{_esc(event.get('summary') or '')}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_dashboard_html(report: dict[str, Any], *, title: str = "Miner Alerts Operations") -> str:
    generated = _timestamp(report.get("generated_ts"))
    summary = report["summary"]
    miner_cards = "".join(_render_miner_card(miner) for miner in report["miners"])
    if not miner_cards:
        miner_cards = '<div class="empty-panel">Sin telemetria disponible</div>'
    state_counts = " ".join(
        f'<span class="count-chip">{_esc(name)} {_esc(count)}</span>'
        for name, count in report.get("state_counts", {}).items()
    ) or '<span class="count-chip">sin estados</span>'
    stability_counts = " ".join(
        f'<span class="count-chip">{_esc(name).upper()} {_esc(count)}</span>'
        for name, count in report.get("stability_counts", {}).items()
    ) or '<span class="count-chip">sin baseline</span>'
    quality_counts = " ".join(
        f'<span class="count-chip">QUALITY {_esc(name).upper()} {_esc(count)}</span>'
        for name, count in report.get("quality_counts", {}).items()
    ) or '<span class="count-chip">sin calidad</span>'
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)}</title>
  <style>
    :root {{ --ink:#18221c; --muted:#667269; --paper:#f4f2e9; --card:#fffdf7; --line:#d8d4c7; --green:#0f6b47; --amber:#b06a09; --red:#a63a2a; --blue:#315e78; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:radial-gradient(circle at 85% 0,#dfe9d8 0,transparent 32rem),linear-gradient(135deg,#f8f5ea,#edf1e8); font-family:"Bahnschrift","Aptos",sans-serif; }}
    main {{ width:min(1440px,calc(100% - 32px)); margin:0 auto; padding:38px 0 64px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:end; border-bottom:2px solid var(--ink); padding-bottom:22px; }}
    h1 {{ margin:4px 0 0; font:700 clamp(2rem,5vw,4.8rem)/.92 Georgia,serif; letter-spacing:-.05em; }}
    h2 {{ font:700 1.5rem Georgia,serif; margin:0; }} h3 {{ margin:3px 0 0; font-size:1.35rem; }}
    .eyebrow {{ margin:0; color:var(--muted); text-transform:uppercase; letter-spacing:.13em; font-size:.72rem; }}
    .generated {{ max-width:340px; text-align:right; color:var(--muted); line-height:1.45; }}
    .kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:22px 0; }}
    .kpi {{ background:rgba(255,253,247,.82); border:1px solid var(--line); padding:18px; border-radius:14px; box-shadow:0 10px 24px rgba(31,45,35,.05); }}
    .kpi span {{ display:block; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; }} .kpi strong {{ font-size:2rem; }}
    .section-head {{ display:flex; justify-content:space-between; gap:16px; align-items:center; margin:34px 0 14px; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:7px; }} .count-chip {{ padding:6px 9px; border:1px solid var(--line); background:var(--card); border-radius:999px; font-size:.78rem; }}
    .miner-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }}
    .miner-card {{ --accent:var(--blue); position:relative; overflow:hidden; background:var(--card); border:1px solid var(--line); border-top:5px solid var(--accent); border-radius:16px; padding:20px; box-shadow:0 14px 30px rgba(31,45,35,.07); }}
    .state-ok {{ --accent:var(--green); }} .state-low,.state-hashboard {{ --accent:var(--amber); }} .state-offline,.state-stale {{ --accent:var(--red); }}
    .miner-head {{ display:flex; justify-content:space-between; gap:12px; align-items:start; }} .state-pill {{ color:white; background:var(--accent); border-radius:999px; padding:6px 9px; font-size:.72rem; font-weight:700; }}
    .primary-rate {{ font:700 2.25rem Georgia,serif; margin-top:20px; }} .primary-rate small {{ font:600 .82rem Bahnschrift,sans-serif; color:var(--muted); }} .freshness {{ margin:2px 0 16px; color:var(--muted); font-size:.82rem; }}
    .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }} .metrics div {{ background:#f1efe6; border-radius:9px; padding:9px; }} .metrics span,.decision span {{ display:block; color:var(--muted); font-size:.7rem; }} .metrics strong {{ font-size:.88rem; }}
    .stability,.quality {{ margin-top:12px; padding:11px; border:1px solid var(--line); border-left:4px solid var(--blue); border-radius:10px; background:#f8f6ee; }} .stability-watch,.quality-watch {{ border-left-color:var(--amber); }} .stability-critical,.quality-critical {{ border-left-color:var(--red); }} .stability-stable,.quality-stable {{ border-left-color:var(--green); }} .stability div,.quality div {{ display:flex; justify-content:space-between; gap:12px; }} .stability span,.quality span {{ color:var(--muted); font-size:.72rem; }} .stability strong,.quality strong {{ font-size:.78rem; }} .stability ul,.quality ul {{ margin:7px 0 0; padding-left:18px; color:var(--muted); font-size:.74rem; }} .baseline {{ margin:6px 0 0; color:var(--muted); font-size:.72rem; }}
    .spark {{ width:100%; height:72px; margin:13px 0 6px; overflow:visible; }} .spark polyline {{ fill:none; stroke:var(--accent); stroke-width:3; stroke-linecap:round; stroke-linejoin:round; }} .threshold-line {{ stroke:#a9a395; stroke-width:1; stroke-dasharray:4 4; }} .spark-empty {{ height:72px; display:grid; place-items:center; color:var(--muted); font-size:.78rem; }}
    .decision {{ display:flex; justify-content:space-between; align-items:end; gap:10px; border-top:1px solid var(--line); padding-top:11px; }} .decision strong {{ text-align:right; font-size:.82rem; }}
    .table-wrap {{ overflow:auto; background:var(--card); border:1px solid var(--line); border-radius:14px; }} table {{ width:100%; border-collapse:collapse; min-width:760px; }} th,td {{ text-align:left; padding:12px 14px; border-bottom:1px solid var(--line); font-size:.82rem; }} th {{ color:var(--muted); text-transform:uppercase; letter-spacing:.07em; font-size:.68rem; }} tr:last-child td {{ border-bottom:0; }}
    .severity,.decision-tag {{ display:inline-block; border-radius:999px; padding:4px 7px; background:#e8e6dd; font-size:.7rem; font-weight:700; }} .empty-panel,.empty-cell {{ padding:36px; text-align:center; color:var(--muted); background:var(--card); border:1px dashed var(--line); border-radius:14px; }}
    footer {{ margin-top:36px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:.78rem; }}
    @media (max-width:800px) {{ header {{ align-items:start; flex-direction:column; }} .generated {{ text-align:left; }} .kpis {{ grid-template-columns:repeat(2,1fr); }} main {{ width:min(100% - 20px,1440px); padding-top:22px; }} }}
  </style>
</head>
<body>
<main>
  <header><div><p class="eyebrow">ASIC fleet / evidencia local</p><h1>{_esc(title)}</h1></div><div class="generated">Generado: {_esc(generated)}<br>Ventana: {_number(report.get('hours'),1,' h')} / stale: {_number(report.get('stale_after_seconds'),0,' s')}</div></header>
  <section class="kpis" aria-label="Resumen de flota">
    <div class="kpi"><span>Mineros</span><strong>{_esc(summary['miners'])}</strong></div>
    <div class="kpi"><span>Saludables</span><strong>{_esc(summary['healthy'])}</strong></div>
    <div class="kpi"><span>Degradados</span><strong>{_esc(summary['degraded'])}</strong></div>
    <div class="kpi"><span>Eventos</span><strong>{_esc(summary['events'])}</strong></div>
    <div class="kpi"><span>Decisiones</span><strong>{_esc(summary['decisions'])}</strong></div>
  </section>
  <section><div class="section-head"><div><h2>Estado actual</h2><p class="eyebrow">Stability Advisor + Mining Quality</p></div><div class="chips">{state_counts} {stability_counts} {quality_counts}</div></div><div class="miner-grid">{miner_cards}</div></section>
  <section><div class="section-head"><h2>Incidentes recientes</h2></div><div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Miner</th><th>Severidad</th><th>Tipo</th><th>Resumen</th></tr></thead><tbody>{_render_event_rows(report['events'])}</tbody></table></div></section>
  <section><div class="section-head"><h2>Vnish Firmware Timeline</h2></div><div class="table-wrap"><table><thead><tr><th>Fecha origen</th><th>Miner</th><th>Severidad</th><th>Categoria</th><th>Codigo</th><th>Resumen</th></tr></thead><tbody>{_render_firmware_rows(report['firmware_events'])}</tbody></table></div></section>
  <section><div class="section-head"><h2>Decisiones de auto-reboot</h2></div><div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Miner</th><th>Resultado</th><th>Hashrate</th><th>Temp</th></tr></thead><tbody>{_render_decision_rows(report['decisions'])}</tbody></table></div></section>
  <footer>Reporte read-only. `chain_voltage` representa evidencia de hashboard, no voltaje AC de entrada. Telegram permanece como superficie de control.</footer>
</main>
</body>
</html>
"""


def generate_dashboard(
    db_path: Path,
    output_path: Path,
    *,
    hours: float = 24.0,
    now_ts: Optional[float] = None,
    stale_after_seconds: float = 900.0,
    row_limit: int = 5_000,
    title: str = "Miner Alerts Operations",
    min_stability_samples: int = 12,
    min_quality_intervals: int = 3,
) -> Path:
    connection = open_read_only(db_path)
    try:
        report = build_dashboard_data(
            connection,
            hours=hours,
            now_ts=now_ts,
            stale_after_seconds=stale_after_seconds,
            row_limit=row_limit,
            min_stability_samples=min_stability_samples,
            min_quality_intervals=min_quality_intervals,
        )
    finally:
        connection.close()
    rendered = render_dashboard_html(report, title=title)
    resolved_output = output_path.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(rendered, encoding="utf-8")
    return resolved_output


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Miner Alerts operations dashboard")
    parser.add_argument("--db", default="data/miner_alerts.db", help="SQLite database path")
    parser.add_argument("--out", default="diagnostics/dashboard/index.html", help="HTML output path")
    parser.add_argument("--hours", type=float, default=24.0, help="History window in hours")
    parser.add_argument("--stale-after-seconds", type=float, default=900.0)
    parser.add_argument("--row-limit", type=int, default=5_000)
    parser.add_argument("--min-stability-samples", type=int, default=12)
    parser.add_argument("--min-quality-intervals", type=int, default=3)
    parser.add_argument("--title", default="Miner Alerts Operations")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        output = generate_dashboard(
            Path(args.db),
            Path(args.out),
            hours=args.hours,
            stale_after_seconds=args.stale_after_seconds,
            row_limit=args.row_limit,
            title=args.title,
            min_stability_samples=args.min_stability_samples,
            min_quality_intervals=args.min_quality_intervals,
        )
    except (FileNotFoundError, OSError, sqlite3.Error, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"DASHBOARD generated={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
