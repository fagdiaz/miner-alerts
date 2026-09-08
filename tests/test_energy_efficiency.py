import unittest
import time
from pathlib import Path
from typing import Optional

from app.energy_efficiency import (
    calculate_efficiency_j_th,
    assess_miner_efficiency,
    build_efficiency_table_text,
    build_miner_efficiency_detail_text,
    evaluate_efficiency_alerts,
    fetch_latest_efficiency_assessments,
    EfficiencyAssessment,
    STATUS_OPTIMAL,
    STATUS_NORMAL,
    STATUS_ELEVATED,
    STATUS_DEGRADED,
    STATUS_UNKNOWN,
)


class TestEnergyEfficiency(unittest.TestCase):
    def test_calculate_efficiency_j_th(self):
        # 2800 W / 100 TH/s = 28.0 J/TH
        self.assertAlmostEqual(calculate_efficiency_j_th(2800.0, 100.0), 28.0, places=2)
        # 3050 W / 104 TH/s = 29.33 J/TH
        self.assertAlmostEqual(calculate_efficiency_j_th(3050.0, 104.0), 29.33, places=2)
        # 0 TH/s -> None (no division by zero)
        self.assertIsNone(calculate_efficiency_j_th(2800.0, 0.0))
        # Negative or None -> None
        self.assertIsNone(calculate_efficiency_j_th(None, 100.0))
        self.assertIsNone(calculate_efficiency_j_th(2800.0, None))
        self.assertIsNone(calculate_efficiency_j_th(0.0, 100.0))

    def test_assess_miner_efficiency_optimal(self):
        assessment = assess_miner_efficiency(
            miner_name="S19JPRO-23",
            power_w=2750.0,
            rate_ths=100.0,
        )
        self.assertEqual(assessment.status, STATUS_OPTIMAL)
        self.assertIn("ÓPTIMA", assessment.status_label)
        self.assertAlmostEqual(assessment.efficiency_j_th, 27.5, places=1)
        self.assertIn("excelente", assessment.recommendation.lower())

    def test_assess_miner_efficiency_normal(self):
        assessment = assess_miner_efficiency(
            miner_name="S19JPRO-24",
            power_w=3000.0,
            rate_ths=100.0,
        )
        self.assertEqual(assessment.status, STATUS_NORMAL)
        self.assertIn("NORMAL", assessment.status_label)
        self.assertAlmostEqual(assessment.efficiency_j_th, 30.0, places=1)

    def test_assess_miner_efficiency_elevated(self):
        assessment = assess_miner_efficiency(
            miner_name="S19JPRO-25",
            power_w=3300.0,
            rate_ths=100.0,
        )
        self.assertEqual(assessment.status, STATUS_ELEVATED)
        self.assertIn("ELEVADA", assessment.status_label)
        self.assertAlmostEqual(assessment.efficiency_j_th, 33.0, places=1)

    def test_assess_miner_efficiency_degraded(self):
        # 3000 W / 70 TH/s = 42.86 J/TH
        assessment = assess_miner_efficiency(
            miner_name="S19JPRO-26",
            power_w=3000.0,
            rate_ths=70.0,
        )
        self.assertEqual(assessment.status, STATUS_DEGRADED)
        self.assertIn("DEGRADADA", assessment.status_label)
        self.assertAlmostEqual(assessment.efficiency_j_th, 42.86, places=1)
        self.assertIn("degradada", assessment.recommendation.lower())

    def test_assess_miner_efficiency_unknown(self):
        assessment = assess_miner_efficiency(
            miner_name="S19JPRO-99",
            power_w=None,
            rate_ths=None,
        )
        self.assertEqual(assessment.status, STATUS_UNKNOWN)
        self.assertIn("SIN DATOS", assessment.status_label)

    def test_build_efficiency_table_text(self):
        assessments = [
            EfficiencyAssessment(
                miner_name="S19JPRO-23",
                status=STATUS_OPTIMAL,
                status_label="🟢 ÓPTIMA",
                rate_ths=100.0,
                power_w=2750.0,
                efficiency_j_th=27.5,
                recommendation="Excelente.",
            ),
            EfficiencyAssessment(
                miner_name="S19JPRO-24",
                status=STATUS_DEGRADED,
                status_label="🟠 DEGRADADA",
                rate_ths=70.0,
                power_w=3000.0,
                efficiency_j_th=42.86,
                recommendation="Degradada.",
            ),
        ]
        text = build_efficiency_table_text(assessments)
        self.assertIn("Eficiencia Energética", text)
        self.assertIn("S19JPRO-23: 🟢 ÓPTIMA", text)
        self.assertIn("27.5 J/TH", text)
        self.assertIn("S19JPRO-24: 🟠 DEGRADADA", text)
        self.assertIn("42.9 J/TH", text)
        self.assertIn("Promedio Flota", text)
        self.assertIn("S19JPRO-24", text)
        self.assertIn("/efficiency <minero>", text)

    def test_build_miner_efficiency_detail_text(self):
        assessment = EfficiencyAssessment(
            miner_name="S19JPRO-26",
            status=STATUS_DEGRADED,
            status_label="🟠 DEGRADADA",
            rate_ths=74.0,
            power_w=3070.0,
            efficiency_j_th=41.49,
            recommendation="Inspeccionar chips con errores o caídas de tensión.",
        )
        text = build_miner_efficiency_detail_text(assessment)
        self.assertIn("Diagnóstico de Eficiencia — S19JPRO-26", text)
        self.assertIn("• Estado: 🟠 DEGRADADA", text)
        self.assertIn("41.5 J/TH", text)
        self.assertIn("74.0 TH/s", text)
        self.assertIn("3,070 W", text)
        self.assertIn("Inspeccionar chips", text)

    def test_evaluate_efficiency_alerts_streak_and_cooldown(self):
        class MockState:
            def __init__(self):
                self.efficiency_streak = 0
                self.last_efficiency_warning_ts = None

        state = MockState()
        now_ts = 1000000.0

        assessment_normal = EfficiencyAssessment(
            miner_name="S19JPRO-26",
            status=STATUS_NORMAL,
            status_label="🟢 NORMAL",
            rate_ths=100.0,
            power_w=2950.0,
            efficiency_j_th=29.5,
            recommendation="OK",
        )

        assessment_degraded = EfficiencyAssessment(
            miner_name="S19JPRO-26",
            status=STATUS_DEGRADED,
            status_label="🟠 DEGRADADA",
            rate_ths=70.0,
            power_w=3000.0,
            efficiency_j_th=42.86,
            recommendation="Degradada",
        )

        config = {
            "efficiency_alert_enabled": True,
            "efficiency_degraded_streak": 3,
            "efficiency_cooldown_seconds": 3600,
        }

        # Tick 1: Degraded -> streak 1, no alert
        alert1 = evaluate_efficiency_alerts(state, assessment_degraded, now_ts, config)
        self.assertIsNone(alert1)
        self.assertEqual(state.efficiency_streak, 1)

        # Tick 2: Degraded -> streak 2, no alert
        alert2 = evaluate_efficiency_alerts(state, assessment_degraded, now_ts + 30, config)
        self.assertIsNone(alert2)
        self.assertEqual(state.efficiency_streak, 2)

        # Tick 3: Degraded -> streak 3 -> fires alert!
        alert3 = evaluate_efficiency_alerts(state, assessment_degraded, now_ts + 60, config)
        self.assertIsNotNone(alert3)
        self.assertIn("[EFICIENCIA]", alert3)
        self.assertIn("S19JPRO-26", alert3)
        self.assertIn("42.9 J/TH", alert3)
        self.assertEqual(state.efficiency_streak, 3)
        self.assertEqual(state.last_efficiency_warning_ts, now_ts + 60)

        # Tick 4: Degraded -> streak 4, within cooldown -> suppressed
        alert4 = evaluate_efficiency_alerts(state, assessment_degraded, now_ts + 90, config)
        self.assertIsNone(alert4)
        self.assertEqual(state.efficiency_streak, 4)

        # Tick 5: Normal -> streak resets to 0
        alert5 = evaluate_efficiency_alerts(state, assessment_normal, now_ts + 120, config)
        self.assertIsNone(alert5)
        self.assertEqual(state.efficiency_streak, 0)

    def test_fetch_latest_efficiency_assessments_db(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = Path(tf.name)

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE telemetry_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_ts REAL NOT NULL,
                    miner_key TEXT NOT NULL,
                    miner_name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    state TEXT NOT NULL,
                    rate_ths REAL,
                    chain_power_w_total REAL
                )
            """)
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, chain_power_w_total) "
                "VALUES (100.0, '192.168.100.23', 'S19JPRO-23', '192.168.100.23', 'OK', 100.0, 2800.0)"
            )
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, chain_power_w_total) "
                "VALUES (101.0, '192.168.100.24', 'S19JPRO-24', '192.168.100.24', 'OK', 70.0, 2940.0)"
            )
            conn.commit()
            conn.close()

            miners = [
                {"name": "S19JPRO-23", "ip": "192.168.100.23"},
                {"name": "S19JPRO-24", "ip": "192.168.100.24"},
                {"name": "S19JPRO-25", "ip": "192.168.100.25"},
            ]

            assessments = fetch_latest_efficiency_assessments(db_path, miners)
            self.assertEqual(len(assessments), 3)

            # Miner 23: 28.0 J/TH (Optimal)
            self.assertEqual(assessments[0].miner_name, "S19JPRO-23")
            self.assertEqual(assessments[0].status, STATUS_OPTIMAL)
            self.assertAlmostEqual(assessments[0].efficiency_j_th, 28.0, places=1)

            # Miner 24: 42.0 J/TH (Degraded)
            self.assertEqual(assessments[1].miner_name, "S19JPRO-24")
            self.assertEqual(assessments[1].status, STATUS_DEGRADED)
            self.assertAlmostEqual(assessments[1].efficiency_j_th, 42.0, places=1)

            # Miner 25: Unknown
            self.assertEqual(assessments[2].miner_name, "S19JPRO-25")
            self.assertEqual(assessments[2].status, STATUS_UNKNOWN)
        finally:
            if db_path.exists():
                db_path.unlink()


class TestEnergyEfficiencyIntegration(unittest.TestCase):
    def test_efficiency_state_persistence(self):
        import tempfile
        import json
        from pathlib import Path
        from app.miner_monitor import save_state, load_state, MinerState

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            st = MinerState(efficiency_streak=3, last_efficiency_warning_ts=1700000000.0)
            states = {"192.168.100.23": st}
            save_state(state_file, states, last_update_id=55)

            raw = json.loads(state_file.read_text(encoding="utf-8"))
            miner_data = raw["states"]["192.168.100.23"]
            self.assertEqual(miner_data.get("efficiency_streak"), 3)
            self.assertEqual(miner_data.get("last_efficiency_warning_ts"), 1700000000.0)

            loaded_states, last_id = load_state(state_file)
            self.assertEqual(last_id, 55)
            loaded_st = loaded_states["192.168.100.23"]
            self.assertEqual(loaded_st.efficiency_streak, 3)
            self.assertEqual(loaded_st.last_efficiency_warning_ts, 1700000000.0)

    def test_efficiency_benchmark_on_real_db_if_present(self):
        real_db = Path("data/miner_alerts.db")
        if not real_db.exists():
            return
        import time
        from app.energy_efficiency import fetch_latest_efficiency_assessments, build_efficiency_table_text

        miners = [
            {"name": "S19JPRO-23", "ip": "192.168.100.23"},
            {"name": "S19JPRO-24", "ip": "192.168.100.24"},
            {"name": "S19JPRO-25", "ip": "192.168.100.25"},
            {"name": "S19JPRO-26", "ip": "192.168.100.26"},
        ]
        t0 = time.perf_counter()
        assessments = fetch_latest_efficiency_assessments(real_db, miners)
        t_query = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        table = build_efficiency_table_text(assessments)
        t_format = (time.perf_counter() - t1) * 1000.0

        self.assertLess(t_query, 100.0, f"Query took {t_query:.1f}ms, expected < 100ms")
        self.assertIn("Eficiencia Energética", table)
        self.assertEqual(len(assessments), 4)


if __name__ == "__main__":
    unittest.main()

