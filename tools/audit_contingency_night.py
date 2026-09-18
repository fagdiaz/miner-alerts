#!/usr/bin/env python3
"""Contingency & Stabilization Night Audit Tool (PROP-009).

Analyzes SQLite operational events, telemetry samples, chain telemetry, and
firmware events to evaluate multi-restart stabilization behavior, elevator cascades,
and empirical evidence for the 5 hypotheses.

Usage:
    & ".\\.venv\\Scripts\\python.exe" tools\\audit_contingency_night.py [--hours 12] [--db data/miner_alerts.db]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple


def open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Database not found: {resolved}")
    conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _format_epoch(ts: Optional[float]) -> str:
    if ts is None:
        return "--:--:--"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_local(ts: Optional[float]) -> str:
    if ts is None:
        return "--:--:--"
    try:
        # Local system timezone
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return _format_epoch(ts)


def audit_contingency_night(
    conn: sqlite3.Connection,
    hours: float = 12.0,
) -> Dict[str, Any]:
    now_ts = datetime.now().timestamp()
    since_ts = now_ts - (hours * 3600.0)

    results: Dict[str, Any] = {
        "since_ts": since_ts,
        "since_local": _format_local(since_ts),
        "now_local": _format_local(now_ts),
        "hours": hours,
        "restarts_by_miner": defaultdict(list),
        "cascade_events": [],
        "chain_break_events": [],
        "stabilization_episodes": [],
        "hypotheses_evidence": {
            "h1_unapplied_presets": 0,
            "h2_vnish_switcher_active": 0,
            "h3_simultaneous_surges": 0,
            "h4_cold_chip_events": 0,
            "h5_warmup_interruptions": 0,
        },
    }

    # 1. Operational Events: Restarts, Cascades, and Interventions
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, occurred_ts, miner_name, event_type, severity, classification, summary, details_json
        FROM operational_events
        WHERE occurred_ts >= ?
        ORDER BY occurred_ts ASC
        """,
        (since_ts,),
    )
    for row in cur.fetchall():
        ev_type = str(row["event_type"])
        m_name = str(row["miner_name"])
        dt_str = _format_local(row["occurred_ts"])
        details = {}
        if row["details_json"]:
            try:
                details = json.loads(row["details_json"])
            except Exception:
                pass

        if "restart" in ev_type:
            results["restarts_by_miner"][m_name].append({
                "id": row["id"],
                "ts": row["occurred_ts"],
                "local_time": dt_str,
                "event_type": ev_type,
                "summary": row["summary"],
                "details": details,
            })

        if ev_type == "elevator_cascade_restart":
            results["cascade_events"].append({
                "id": row["id"],
                "ts": row["occurred_ts"],
                "local_time": dt_str,
                "miner": m_name,
                "summary": row["summary"],
                "details": details,
            })

    # 2. Firmware Events: Chain Breaks, Watchdog Reboots, Autotuning
    cur.execute(
        """
        SELECT id, collected_ts, miner_name, category, severity, code, summary
        FROM firmware_events
        WHERE collected_ts >= ? AND (code LIKE '%chain%' OR code LIKE '%reboot%' OR code LIKE '%restart%' OR code LIKE '%stop%')
        ORDER BY collected_ts ASC
        """,
        (since_ts,),
    )
    for row in cur.fetchall():
        results["chain_break_events"].append({
            "id": row["id"],
            "ts": row["collected_ts"],
            "local_time": _format_local(row["collected_ts"]),
            "miner": row["miner_name"],
            "code": row["code"],
            "summary": row["summary"],
        })

    # 3. Telemetry Samples: Cold-Chip temperatures (< 65C) during low hashrate
    cur.execute(
        """
        SELECT observed_ts, miner_name, state, rate_ths, active_boards, max_temp_c, chain_power_w_total, elapsed_seconds
        FROM telemetry_samples
        WHERE observed_ts >= ? AND max_temp_c IS NOT NULL
        ORDER BY observed_ts ASC
        """,
        (since_ts,),
    )
    for row in cur.fetchall():
        temp = float(row["max_temp_c"])
        elap = int(row["elapsed_seconds"]) if row["elapsed_seconds"] is not None else 0
        rate = float(row["rate_ths"]) if row["rate_ths"] is not None else 0.0
        if elap < 300 and temp < 60.0 and rate < 50.0:
            results["hypotheses_evidence"]["h4_cold_chip_events"] += 1

    return results


def print_report(audit: Dict[str, Any]) -> None:
    print("=" * 80)
    print(f"  MINER ALERTS: AUDITORÍA NOCTURNA DE CONTINGENCIA & ESTABILIZACIÓN (PROP-009)")
    print(f"  Ventana: {audit['since_local']}  -->  {audit['now_local']} ({audit['hours']:.1f} horas)")
    print("=" * 80)

    restarts = audit["restarts_by_miner"]
    total_restarts = sum(len(evs) for evs in restarts.values())
    print(f"\n[1] RESUMEN GLOBAL DE REINICIOS ({total_restarts} eventos detectados):")
    if not restarts:
        print("    No se registraron reinicios en la ventana de observación.")
    else:
        for miner, evs in sorted(restarts.items()):
            print(f"    • {miner:12s}: {len(evs)} reinicio(s)")
            for ev in evs[-4:]:  # last 4
                print(f"        - [{ev['local_time']}] {ev['summary']}")

    cascades = audit["cascade_events"]
    print(f"\n[2] REINICIOS CORRELACIONADOS EN ELEVADORES (CASCADA) ({len(cascades)} eventos):")
    if not cascades:
        print("    Ninguna caída en cascada registrada en esta ventana.")
    else:
        for c in cascades:
            print(f"    • [{c['local_time']}] Minero: {c['miner']} | {c['summary']}")

    fw_breaks = audit["chain_break_events"]
    print(f"\n[3] EVENTOS INTERNOS DE FIRMWARE VNISH (CORTES/WATCHDOG) ({len(fw_breaks)} eventos):")
    if not fw_breaks:
        print("    Ningún corte interno registrado en firmware.")
    else:
        for b in fw_breaks[-8:]:
            print(f"    • [{b['local_time']}] {b['miner']:12s} [{b['code']}]: {b['summary']}")

    ev = audit["hypotheses_evidence"]
    print(f"\n[4] INDICADORES EMPÍRICOS DE HIPÓTESIS:")
    print(f"    • H4 (Muestras de silicio frío < 60°C en fase de arranque): {ev['h4_cold_chip_events']}")
    print(f"    • Eventos en cascada entre pares del mismo elevador:         {len(cascades)}")
    print("=" * 80)
    print("  Conclusión preliminar: Revisar correlación temporal con PROP-009 en docs/proposals/.")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoría de contingencia nocturna")
    parser.add_argument("--hours", type=float, default=12.0, help="Horas hacia atrás a inspeccionar (def: 12)")
    parser.add_argument("--db", type=str, default="data/miner_alerts.db", help="Ruta a la BD SQLite")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Base de datos no encontrada en {db_path}")
        sys.exit(1)

    conn = open_read_only(db_path)
    try:
        audit = audit_contingency_night(conn, hours=args.hours)
        print_report(audit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
