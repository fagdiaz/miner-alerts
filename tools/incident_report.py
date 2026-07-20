#!/usr/bin/env python3
"""Generate a read-only incident report from the Miner Alerts SQLite store."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional


def open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _query_rows(
    connection: sqlite3.Connection,
    table_name: str,
    timestamp_column: str,
    *,
    since_ts: float,
    miner: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, table_name):
        return []
    clauses = [f"{timestamp_column} >= ?"]
    params: list[Any] = [float(since_ts)]
    if miner:
        clauses.append("(miner_name = ? OR miner_key = ? OR miner_key LIKE ?)")
        params.extend([miner, miner, f"%-{miner}|%"])
    params.append(int(limit))
    rows = connection.execute(
        f"""
        SELECT * FROM {table_name}
        WHERE {' AND '.join(clauses)}
        ORDER BY {timestamp_column} DESC, id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def build_report(
    connection: sqlite3.Connection,
    *,
    hours: float,
    miner: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> dict[str, Any]:
    effective_now = time.time() if now_ts is None else float(now_ts)
    safe_hours = max(0.1, min(float(hours), 24.0 * 365.0))
    since_ts = effective_now - safe_hours * 3600.0
    samples = _query_rows(
        connection,
        "telemetry_samples",
        "observed_ts",
        since_ts=since_ts,
        miner=miner,
        limit=100_000,
    )
    events = _query_rows(
        connection,
        "operational_events",
        "occurred_ts",
        since_ts=since_ts,
        miner=miner,
        limit=10_000,
    )
    decisions = _query_rows(
        connection,
        "reboot_decisions",
        "evaluated_ts",
        since_ts=since_ts,
        miner=miner,
        limit=100_000,
    )

    rates = [float(row["rate_ths"]) for row in samples if row.get("rate_ths") is not None]
    temperatures = [
        float(row["max_temp_c"])
        for row in samples
        if row.get("max_temp_c") is not None
    ]
    voltages = [
        float(row["chain_voltage_mv_avg"])
        for row in samples
        if row.get("chain_voltage_mv_avg") is not None
    ]
    powers = [
        float(row["chain_power_w_total"])
        for row in samples
        if row.get("chain_power_w_total") is not None
    ]
    miners = sorted(
        {
            str(row.get("miner_name"))
            for row in [*samples, *events, *decisions]
            if row.get("miner_name")
        }
    )
    return {
        "generated_ts": effective_now,
        "since_ts": since_ts,
        "hours": safe_hours,
        "miner_filter": miner,
        "miners": miners,
        "counts": {
            "samples": len(samples),
            "events": len(events),
            "decisions": len(decisions),
        },
        "signals": {
            "rate_ths_min": min(rates) if rates else None,
            "rate_ths_avg": _average(rates),
            "rate_ths_max": max(rates) if rates else None,
            "max_temp_c": max(temperatures) if temperatures else None,
            "chain_voltage_mv_avg": _average(voltages),
            "chain_power_w_avg": _average(powers),
        },
        "state_counts": dict(sorted(Counter(str(row.get("state")) for row in samples).items())),
        "event_counts": dict(sorted(Counter(str(row.get("event_type")) for row in events).items())),
        "decision_counts": dict(sorted(Counter(str(row.get("result")) for row in decisions).items())),
        "latest_events": events[:10],
        "latest_decisions": decisions[:10],
    }


def _value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def render_markdown(report: dict[str, Any]) -> str:
    signals = report["signals"]
    lines = [
        "# Miner Alerts Incident Report",
        "",
        f"- Window: {report['hours']:.1f} hours",
        f"- Miner filter: {report.get('miner_filter') or 'all'}",
        f"- Miners: {', '.join(report['miners']) or 'none'}",
        f"- Samples: {report['counts']['samples']}",
        f"- Events: {report['counts']['events']}",
        f"- Reboot decisions: {report['counts']['decisions']}",
        "",
        "## Signal Summary",
        "",
        f"- Hashrate min/avg/max: {_value(signals['rate_ths_min'])} / {_value(signals['rate_ths_avg'])} / {_value(signals['rate_ths_max'])} TH/s",
        f"- Maximum temperature: {_value(signals['max_temp_c'], ' C')}",
        f"- Average chain voltage: {_value(signals['chain_voltage_mv_avg'], ' mV')} (not AC input voltage)",
        f"- Average chain consumption: {_value(signals['chain_power_w_avg'], ' W')}",
        "",
        "## State Counts",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in report["state_counts"].items())
    if not report["state_counts"]:
        lines.append("- No samples")
    lines.extend(["", "## Reboot Decision Counts", ""])
    lines.extend(f"- {name}: {count}" for name, count in report["decision_counts"].items())
    if not report["decision_counts"]:
        lines.append("- No decisions")
    lines.extend(["", "## Event Counts", ""])
    lines.extend(f"- {name}: {count}" for name, count in report["event_counts"].items())
    if not report["event_counts"]:
        lines.append("- No events")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Miner Alerts incident report")
    parser.add_argument("--db", default="data/miner_alerts.db", help="SQLite database path")
    parser.add_argument("--hours", type=float, default=24.0, help="Report window")
    parser.add_argument("--miner", help="Optional miner display name/key")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--out", help="Optional output file; stdout when omitted")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        connection = open_read_only(Path(args.db))
    except (FileNotFoundError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        report = build_report(connection, hours=args.hours, miner=args.miner)
    finally:
        connection.close()
    output = (
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_markdown(report)
    )
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
