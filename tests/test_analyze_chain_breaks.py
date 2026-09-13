"""Unit tests for tools/analyze_chain_breaks.py (Spec 054)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.core.event_store import EventStore
from tools.analyze_chain_breaks import (
    analyze_chain_telemetry,
    main,
    open_read_only,
    render_terminal_report,
)


class AnalyzeChainBreaksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_alerts.db"
        self.store = EventStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_analyze_empty_database(self) -> None:
        conn = open_read_only(self.db_path)
        try:
            result = analyze_chain_telemetry(conn, since_ts=0.0)
            self.assertEqual(result["total_samples"], 0)
            self.assertEqual(result["miners"], {})
        finally:
            conn.close()

    def test_analyze_samples_and_correlations(self) -> None:
        # 1. Insert chain samples
        samples_c1 = {
            "chain_id": 1,
            "state": "mining",
            "hr_realtime_mhs": 33100.0,
            "hr_nominal_mhs": 33000.0,
            "hr_deficit_pct": 0.0,
            "freq_mhz_avg": 540.0,
            "sensors_error_count": 0,
            "sensors_json": json.dumps([{"state": "measure", "board": 45, "chip": 60, "loc": 28}]),
            "chips_error_count": 0,
            "chips_throttled_count": 0,
        }
        samples_c2 = {
            "chain_id": 2,
            "state": "mining",
            "hr_realtime_mhs": 33200.0,
            "hr_nominal_mhs": 33000.0,
            "hr_deficit_pct": 0.0,
            "freq_mhz_avg": 540.0,
            "sensors_error_count": 1,
            "sensors_json": json.dumps([{"state": "error", "board": 39, "chip": 54, "loc": 28}]),
            "chips_error_count": 2,
            "chips_throttled_count": 1,
        }
        self.store.record_chain_samples(
            miner_key="S19JPRO-24",
            observed_ts=1000.0,
            samples=[samples_c1, samples_c2],
        )

        # 2. Insert operational event with culprit_chain
        details = {
            "culprit_chain": {
                "chain_id": 2,
                "reason": "Falla sensor I2C (loc 28)",
                "faulty_locs": [28],
            }
        }
        self.store.record_event(
            occurred_ts=1050.0,
            miner_key="S19JPRO-24",
            miner_name="24",
            host="192.168.100.24",
            event_type="reboot_detected",
            severity="warning",
            summary="Reinicio con corte de cadena",
            details=details,
        )

        conn = open_read_only(self.db_path)
        try:
            analysis = analyze_chain_telemetry(conn, since_ts=900.0)
            self.assertEqual(analysis["total_samples"], 2)
            self.assertIn("S19JPRO-24", analysis["miners"])
            m_data = analysis["miners"]["S19JPRO-24"]
            self.assertEqual(m_data["sample_count"], 2)

            # Check Chain 1
            c1 = m_data["chains"][1]
            self.assertEqual(c1["sensor_error_count"], 0)
            self.assertEqual(c1["sensor_error_pct"], 0.0)

            # Check Chain 2
            c2 = m_data["chains"][2]
            self.assertEqual(c2["sensor_error_count"], 1)
            self.assertEqual(c2["sensor_error_pct"], 100.0)
            self.assertEqual(c2["faulty_locs"], {28: 1})
            self.assertEqual(c2["max_chip_errors"], 2)
            self.assertEqual(c2["max_chips_throttled"], 1)

            # Check Incident Correlation
            correlations = analysis["correlations"]
            self.assertEqual(len(correlations), 1)
            corr = correlations[0]
            self.assertEqual(corr["miner_key"], "S19JPRO-24")
            self.assertEqual(corr["culprit_chain_id"], 2)
            self.assertEqual(corr["faulty_locs"], [28])

            # Check Terminal Report rendering
            report_text = render_terminal_report(analysis)
            self.assertIn("INFORME DE SALUD DE CADENAS", report_text)
            self.assertIn("S19JPRO-24", report_text)
            self.assertIn("Cadena 2", report_text)
            self.assertIn("WARN [1 errs]", report_text)
            self.assertIn("Culpable: Cadena 2", report_text)
        finally:
            conn.close()

    def test_cli_main_execution(self) -> None:
        ret = main(["--db", str(self.db_path), "--days", "1", "--json"])
        self.assertEqual(ret, 0)

        # Missing database
        bad_db = self.db_path.parent / "non_existent.db"
        ret_err = main(["--db", str(bad_db)])
        self.assertEqual(ret_err, 1)


if __name__ == "__main__":
    unittest.main()
