#!/usr/bin/env python3
"""Retrospective Chain Break & Hashboard Telemetry Analysis Tool (Spec 054).

Correlates Vnish per-chain telemetry (sensors, chips, hashrate deficits) with
historical operational events and restarts stored in SQLite to identify hardware
degradation patterns and root causes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def open_read_only(path: Path) -> sqlite3.Connection:
    """Open SQLite connection in strict read-only mode."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _format_ts(ts: Optional[float]) -> str:
    if ts is None:
        return "--"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def analyze_chain_telemetry(
    conn: sqlite3.Connection,
    *,
    miner: Optional[str] = None,
    since_ts: float = 0.0,
) -> Dict[str, Any]:
    """Extract and aggregate per-chain metrics and incident correlations."""
    if not _table_exists(conn, "chain_telemetry_samples"):
        return {
            "error": "Tabla 'chain_telemetry_samples' no existe en la base de datos.",
            "total_samples": 0,
            "miners": {},
        }

    where_clauses = ["observed_ts >= ?"]
    params: List[Any] = [float(since_ts)]
    if miner:
        where_clauses.append("(miner_key = ? OR miner_key LIKE ?)")
        params.extend([miner, f"%{miner}%"])

    sql = f"""
        SELECT * FROM chain_telemetry_samples
        WHERE {' AND '.join(where_clauses)}
        ORDER BY observed_ts ASC, chain_id ASC
    """
    rows = conn.execute(sql, params).fetchall()

    if not rows:
        return {
            "total_samples": 0,
            "since_ts": since_ts,
            "miners": {},
            "summary": "No se encontraron muestras de cadenas en el período.",
        }

    # Grouping structures
    miner_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "sample_count": 0,
        "first_ts": None,
        "last_ts": None,
        "chains": defaultdict(lambda: {
            "sample_count": 0,
            "sensor_errors": 0,
            "faulty_locs": Counter(),
            "max_chip_temp": None,
            "max_board_temp": None,
            "chip_errors_sum": 0,
            "chip_errors_max": 0,
            "chips_throttled_max": 0,
            "deficit_samples": 0,
            "fault_samples": 0,
            "hr_realtime_sum": 0.0,
            "hr_nominal_sum": 0.0,
        }),
    })

    for row in rows:
        m_key = row["miner_key"]
        c_id = int(row["chain_id"])
        ts = float(row["observed_ts"])

        m_dict = miner_data[m_key]
        m_dict["sample_count"] += 1
        if m_dict["first_ts"] is None or ts < m_dict["first_ts"]:
            m_dict["first_ts"] = ts
        if m_dict["last_ts"] is None or ts > m_dict["last_ts"]:
            m_dict["last_ts"] = ts

        c_dict = m_dict["chains"][c_id]
        c_dict["sample_count"] += 1

        # Hashrates
        hr_real = float(row["hr_realtime"] or 0.0)
        hr_nom = float(row["hr_nominal"] or 0.0)
        c_dict["hr_realtime_sum"] += hr_real
        c_dict["hr_nominal_sum"] += hr_nom

        deficit_pct = float(row["hr_deficit_pct"] or 0.0)
        if deficit_pct >= 10.0:
            c_dict["deficit_samples"] += 1

        state = str(row["state"] or "").lower()
        if state not in ("mining", "ok") and hr_real <= 0.0:
            c_dict["fault_samples"] += 1

        # Chips
        chips_err = int(row["chips_error_count"] or 0)
        chips_throt = int(row["chips_throttled_count"] or 0)
        c_dict["chip_errors_sum"] += chips_err
        if chips_err > c_dict["chip_errors_max"]:
            c_dict["chip_errors_max"] = chips_err
        if chips_throt > c_dict["chips_throttled_max"]:
            c_dict["chips_throttled_max"] = chips_throt

        # Sensors & I2C
        s_err_cnt = int(row["sensors_error_count"] or 0)
        if s_err_cnt > 0:
            c_dict["sensor_errors"] += 1

        sensors_json = row["sensors_json"]
        if sensors_json:
            try:
                sensors_list = json.loads(sensors_json)
                if isinstance(sensors_list, list):
                    for s in sensors_list:
                        if isinstance(s, dict):
                            if str(s.get("state", "")).lower() != "measure":
                                loc = s.get("loc")
                                if loc is not None:
                                    c_dict["faulty_locs"][int(loc)] += 1
                            c_temp = s.get("chip")
                            if isinstance(c_temp, (int, float)):
                                if c_dict["max_chip_temp"] is None or c_temp > c_dict["max_chip_temp"]:
                                    c_dict["max_chip_temp"] = float(c_temp)
                            b_temp = s.get("board")
                            if isinstance(b_temp, (int, float)):
                                if c_dict["max_board_temp"] is None or b_temp > c_dict["max_board_temp"]:
                                    c_dict["max_board_temp"] = float(b_temp)
            except Exception:
                pass

    # Incident correlation with operational_events (restarts and state transitions)
    correlations = []
    if _table_exists(conn, "operational_events"):
        event_sql = """
            SELECT id, occurred_ts, miner_key, event_type, details_json
            FROM operational_events
            WHERE occurred_ts >= ?
              AND event_type IN ('reboot_detected', 'state_transition')
            ORDER BY occurred_ts DESC
        """
        event_rows = conn.execute(event_sql, (float(since_ts),)).fetchall()
        for ev in event_rows:
            ev_miner = ev["miner_key"]
            ev_ts = float(ev["occurred_ts"])
            ev_type = ev["event_type"]
            ev_id = ev["id"]

            details = {}
            if ev["details_json"]:
                try:
                    details = json.loads(ev["details_json"])
                except Exception:
                    pass

            culprit = details.get("culprit_chain")
            if culprit:
                correlations.append({
                    "event_id": ev_id,
                    "event_type": ev_type,
                    "occurred_ts": ev_ts,
                    "miner_key": ev_miner,
                    "culprit_chain_id": culprit.get("chain_id"),
                    "reason": culprit.get("reason"),
                    "faulty_locs": culprit.get("faulty_locs", []),
                })

    # Prepare final JSON-friendly dict
    formatted_miners = {}
    for m_key, m_val in miner_data.items():
        formatted_chains = {}
        for c_id, c_val in sorted(m_val["chains"].items()):
            n = c_val["sample_count"]
            avg_real = round(c_val["hr_realtime_sum"] / n, 2) if n > 0 else 0.0
            avg_nom = round(c_val["hr_nominal_sum"] / n, 2) if n > 0 else 0.0
            sensor_err_pct = round((c_val["sensor_errors"] / n) * 100.0, 1) if n > 0 else 0.0

            formatted_chains[c_id] = {
                "sample_count": n,
                "sensor_error_count": c_val["sensor_errors"],
                "sensor_error_pct": sensor_err_pct,
                "faulty_locs": dict(c_val["faulty_locs"]),
                "avg_hr_realtime_mhs": avg_real,
                "avg_hr_nominal_mhs": avg_nom,
                "max_chip_temp": c_val["max_chip_temp"],
                "max_board_temp": c_val["max_board_temp"],
                "max_chip_errors": c_val["chip_errors_max"],
                "max_chips_throttled": c_val["chips_throttled_max"],
                "deficit_samples": c_val["deficit_samples"],
                "fault_samples": c_val["fault_samples"],
            }

        formatted_miners[m_key] = {
            "sample_count": m_val["sample_count"],
            "first_ts": m_val["first_ts"],
            "last_ts": m_val["last_ts"],
            "chains": formatted_chains,
        }

    return {
        "total_samples": len(rows),
        "since_ts": since_ts,
        "miners": formatted_miners,
        "correlations": correlations,
    }


def render_terminal_report(analysis: Dict[str, Any]) -> str:
    """Format human-readable CLI report from analysis dict."""
    if "error" in analysis:
        return f"\n[ERROR] {analysis['error']}\n"

    lines = [
        "==================================================================",
        "  INFORME DE SALUD DE CADENAS Y ANÁLISIS DE CHAIN BREAK (Spec 054)",
        "==================================================================",
        f"Muestras totales analizadas: {analysis.get('total_samples', 0)}",
        f"Período desde: {_format_ts(analysis.get('since_ts'))}",
        "------------------------------------------------------------------",
    ]

    miners = analysis.get("miners", {})
    if not miners:
        lines.append("No hay registros de telemetría de cadenas en el período seleccionado.")
        lines.append("==================================================================")
        return "\n".join(lines)

    for m_key, m_data in sorted(miners.items()):
        short_name = m_key.split("|")[0] if "|" in m_key else m_key
        lines.append(f"\n[MINERO] {short_name} ({m_key})")
        lines.append(f"   Muestras: {m_data['sample_count']} | Rango: {_format_ts(m_data['first_ts'])} -> {_format_ts(m_data['last_ts'])}")
        lines.append("   " + "-" * 62)
        lines.append(f"   {'Cadena':<8} {'Estado / Salud':<16} {'Sensor Err %':<14} {'Locs Fallas':<12} {'Max Temp':<10}")
        lines.append("   " + "-" * 62)

        for c_id, c_data in sorted(m_data["chains"].items()):
            err_cnt = c_data["sensor_error_count"]
            err_pct = c_data["sensor_error_pct"]
            if err_cnt == 0:
                health_status = "OK [Saludable]"
            else:
                health_status = f"WARN [{err_cnt} errs]"

            locs_str = ", ".join(f"{loc} (x{cnt})" for loc, cnt in c_data["faulty_locs"].items()) if c_data["faulty_locs"] else "--"
            chip_t = f"{c_data['max_chip_temp']:.0f}°C" if c_data["max_chip_temp"] else "--"
            board_t = f"{c_data['max_board_temp']:.0f}°C" if c_data["max_board_temp"] else "--"
            temp_str = f"{chip_t}/{board_t}"

            lines.append(f"   Cadena {c_id:<3} {health_status:<16} {f'{err_pct}%':<14} {locs_str:<12} {temp_str:<10}")

            if c_data["max_chip_errors"] > 0 or c_data["max_chips_throttled"] > 0:
                lines.append(f"     └ Chips: max_errs={c_data['max_chip_errors']} max_throttled={c_data['max_chips_throttled']}")

    # Incident correlations
    correlations = analysis.get("correlations", [])
    lines.append("\n" + "=" * 66)
    lines.append(f"  CORRELACIÓN CON INCIDENTES Y REINICIOS ({len(correlations)} detectados)")
    lines.append("=" * 66)

    if not correlations:
        lines.append("No se registraron incidentes con causa de cadena física en este período.")
    else:
        for corr in correlations:
            ev_time = _format_ts(corr["occurred_ts"])
            m_name = corr["miner_key"].split("|")[0] if "|" in corr["miner_key"] else corr["miner_key"]
            c_culprit = corr.get("culprit_chain_id")
            reason = corr.get("reason", "Corte físico")
            locs = corr.get("faulty_locs", [])
            loc_str = f" (loc {', '.join(map(str, locs))})" if locs else ""
            lines.append(f"• Evento #{corr['event_id']} [{ev_time}] Minero: {m_name}")
            lines.append(f"  └ Culpable: Cadena {c_culprit} -> {reason}{loc_str}")

    lines.append("==================================================================\n")
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analizar telemetría profunda de hashboards y correlación de cortes de cadena.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/miner_alerts.db"),
        help="Ruta al archivo de base de datos SQLite (default: data/miner_alerts.db).",
    )
    parser.add_argument(
        "--miner",
        type=str,
        default=None,
        help="Filtrar por nombre o IP del minero (ej. 24, S19JPRO-24).",
    )
    parser.add_argument(
        "--days",
        type=float,
        default=7.0,
        help="Días retrospectivos a evaluar (default: 7.0).",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Horas retrospectivas (sobrescribe --days si se especifica).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida estructurada en JSON estándar.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = parse_args(argv)
    if not args.db.exists():
        print(f"Error: La base de datos no existe en '{args.db}'", file=sys.stderr)
        return 1

    try:
        conn = open_read_only(args.db)
    except Exception as exc:
        print(f"Error al abrir la base de datos: {exc}", file=sys.stderr)
        return 1

    now = time.time()
    if args.hours is not None:
        window_s = max(0.1, args.hours) * 3600.0
    else:
        window_s = max(0.1, args.days) * 86400.0
    since_ts = now - window_s

    try:
        analysis = analyze_chain_telemetry(conn, miner=args.miner, since_ts=since_ts)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
    else:
        print(render_terminal_report(analysis))

    return 0


if __name__ == "__main__":
    sys.exit(main())
