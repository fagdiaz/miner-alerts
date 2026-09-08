import unittest
import time
from pathlib import Path
from typing import Optional

from app.fan_health import (
    calculate_thermal_headroom,
    assess_miner_cooling,
    build_fans_table_text,
    build_miner_fan_detail_text,
    evaluate_cooling_alerts,
    CoolingAssessment,
    STATUS_HEALTHY,
    STATUS_ELEVATED,
    STATUS_SATURATED,
    STATUS_CRITICAL_HEAT,
    STATUS_FAN_DEFECT,
    STATUS_UNKNOWN,
)


class TestFanHealth(unittest.TestCase):
    def test_calculate_thermal_headroom(self):
        # 85.0 - 71.5 = 13.5
        self.assertAlmostEqual(calculate_thermal_headroom(71.5), 13.5, places=1)
        # 85.0 - 84.0 = 1.0
        self.assertAlmostEqual(calculate_thermal_headroom(84.0), 1.0, places=1)
        # Over 85 -> bounded to 0.0
        self.assertEqual(calculate_thermal_headroom(87.5), 0.0)
        # None returns None
        self.assertIsNone(calculate_thermal_headroom(None))

    def test_assess_miner_cooling_healthy(self):
        assessment = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=70.0,
            fan_rpm_max=4800,
            fan_pwm_percent=75.0,
            diagnostic_flags=(),
            rate_ths=95.0,
        )
        self.assertEqual(assessment.status, STATUS_HEALTHY)
        self.assertIn("OK", assessment.status_label)
        self.assertAlmostEqual(assessment.thermal_headroom_c, 15.0, places=1)
        self.assertIn("óptimo", assessment.recommendation.lower())

    def test_assess_miner_cooling_elevated(self):
        # Elevated due to temperature >= 75°C
        assessment1 = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=76.0,
            fan_rpm_max=5400,
            fan_pwm_percent=85.0,
            diagnostic_flags=(),
            rate_ths=95.0,
        )
        self.assertEqual(assessment1.status, STATUS_ELEVATED)
        self.assertIn("ELEVADO", assessment1.status_label)

        # Elevated due to PWM >= 90%
        assessment2 = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=72.0,
            fan_rpm_max=5600,
            fan_pwm_percent=92.0,
            diagnostic_flags=(),
            rate_ths=95.0,
        )
        self.assertEqual(assessment2.status, STATUS_ELEVATED)

    def test_assess_miner_cooling_saturated(self):
        # Temp >= 78°C and PWM >= 95%
        assessment = assess_miner_cooling(
            miner_name="S19JPRO-24",
            max_temp_c=79.2,
            fan_rpm_max=6200,
            fan_pwm_percent=97.0,
            diagnostic_flags=(),
            rate_ths=95.0,
        )
        self.assertEqual(assessment.status, STATUS_SATURATED)
        self.assertIn("SATURADO", assessment.status_label)
        self.assertAlmostEqual(assessment.thermal_headroom_c, 5.8, places=1)
        self.assertIn("filtros", assessment.recommendation.lower())

    def test_assess_miner_cooling_critical_heat(self):
        # Temp >= 82°C
        assessment = assess_miner_cooling(
            miner_name="S19JPRO-24",
            max_temp_c=83.5,
            fan_rpm_max=6500,
            fan_pwm_percent=100.0,
            diagnostic_flags=(),
            rate_ths=90.0,
        )
        self.assertEqual(assessment.status, STATUS_CRITICAL_HEAT)
        self.assertIn("CRÍTICO", assessment.status_label)
        self.assertAlmostEqual(assessment.thermal_headroom_c, 1.5, places=1)

    def test_assess_miner_cooling_fan_defect(self):
        # Defect 1: Fan RPM < 2000 while hashing
        assessment1 = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=74.0,
            fan_rpm_max=1200,
            fan_pwm_percent=80.0,
            diagnostic_flags=(),
            rate_ths=85.0,
        )
        self.assertEqual(assessment1.status, STATUS_FAN_DEFECT)
        self.assertIn("DEFECTO", assessment1.status_label)

        # Defect 2: diagnostic_flags contains 'fan_signal_missing'
        assessment2 = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=72.0,
            fan_rpm_max=None,
            fan_pwm_percent=None,
            diagnostic_flags=("fan_signal_missing",),
            rate_ths=85.0,
        )
        self.assertEqual(assessment2.status, STATUS_FAN_DEFECT)

    def test_assess_miner_cooling_unknown(self):
        assessment = assess_miner_cooling(
            miner_name="S19JPRO-99",
            max_temp_c=None,
            fan_rpm_max=None,
            fan_pwm_percent=None,
            diagnostic_flags=(),
            rate_ths=None,
        )
        self.assertEqual(assessment.status, STATUS_UNKNOWN)
        self.assertIn("SIN DATOS", assessment.status_label)

    def test_build_fans_table_text(self):
        assessments = [
            CoolingAssessment(
                miner_name="S19JPRO-23",
                status=STATUS_HEALTHY,
                status_label="🟢 OK",
                max_temp_c=71.2,
                thermal_headroom_c=13.8,
                fan_rpm_max=5400,
                fan_pwm_percent=82.0,
                diagnostic_flags=(),
                recommendation="Disipación adecuada.",
            ),
            CoolingAssessment(
                miner_name="S19JPRO-24",
                status=STATUS_SATURATED,
                status_label="🟠 SATURADO",
                max_temp_c=79.4,
                thermal_headroom_c=5.6,
                fan_rpm_max=6350,
                fan_pwm_percent=98.0,
                diagnostic_flags=(),
                recommendation="Limpiar filtros antipolvo.",
            ),
        ]
        text = build_fans_table_text(assessments)
        self.assertIn("Estado de Enfriamiento", text)
        self.assertIn("S19JPRO-23: 🟢 OK", text)
        self.assertIn("5,400 RPM", text)
        self.assertIn("Margen: 13.8°C", text)
        self.assertIn("S19JPRO-24: 🟠 SATURADO", text)
        self.assertIn("6,350 RPM", text)
        self.assertIn("Margen: 5.6°C", text)
        self.assertIn("/fans <minero>", text)

    def test_build_miner_fan_detail_text(self):
        assessment = CoolingAssessment(
            miner_name="S19JPRO-24",
            status=STATUS_SATURATED,
            status_label="🟠 SATURADO",
            max_temp_c=79.4,
            thermal_headroom_c=5.6,
            fan_rpm_max=6350,
            fan_pwm_percent=98.0,
            diagnostic_flags=("high_temperature",),
            recommendation="Inspeccionar y limpiar filtros antipolvo.",
        )
        text = build_miner_fan_detail_text(assessment)
        self.assertIn("Diagnóstico de Enfriamiento — S19JPRO-24", text)
        self.assertIn("• Estado: 🟠 SATURADO", text)
        self.assertIn("• Temp. Máxima: 79.4°C", text)
        self.assertIn("• Margen Térmico: 5.6°C", text)
        self.assertIn("• Velocidad Fans: 6,350 RPM", text)
        self.assertIn("• Potencia PWM: 98.0%", text)
        self.assertIn("Inspeccionar y limpiar filtros antipolvo", text)

    def test_evaluate_cooling_alerts_streak_and_cooldown(self):
        # Miner state mock
        class MockState:
            def __init__(self):
                self.cooling_streak = 0
                self.last_cooling_warning_ts = None

        state = MockState()
        now_ts = 1000000.0

        assessment_healthy = CoolingAssessment(
            miner_name="S19JPRO-24",
            status=STATUS_HEALTHY,
            status_label="🟢 OK",
            max_temp_c=70.0,
            thermal_headroom_c=15.0,
            fan_rpm_max=4800,
            fan_pwm_percent=75.0,
            diagnostic_flags=(),
            recommendation="OK",
        )

        assessment_saturated = CoolingAssessment(
            miner_name="S19JPRO-24",
            status=STATUS_SATURATED,
            status_label="🟠 SATURADO",
            max_temp_c=79.5,
            thermal_headroom_c=5.5,
            fan_rpm_max=6300,
            fan_pwm_percent=98.0,
            diagnostic_flags=(),
            recommendation="Limpiar filtros.",
        )

        config = {
            "cooling_alert_enabled": True,
            "cooling_saturate_streak": 3,
            "cooling_cooldown_seconds": 3600,
        }

        # Tick 1: Saturated -> streak becomes 1, no alert
        alert1 = evaluate_cooling_alerts(state, assessment_saturated, now_ts, config)
        self.assertIsNone(alert1)
        self.assertEqual(state.cooling_streak, 1)

        # Tick 2: Saturated -> streak becomes 2, no alert
        alert2 = evaluate_cooling_alerts(state, assessment_saturated, now_ts + 30, config)
        self.assertIsNone(alert2)
        self.assertEqual(state.cooling_streak, 2)

        # Tick 3: Saturated -> streak becomes 3 -> alert fires!
        alert3 = evaluate_cooling_alerts(state, assessment_saturated, now_ts + 60, config)
        self.assertIsNotNone(alert3)
        self.assertIn("[ENFRIAMIENTO]", alert3)
        self.assertIn("S19JPRO-24", alert3)
        self.assertEqual(state.cooling_streak, 3)
        self.assertEqual(state.last_cooling_warning_ts, now_ts + 60)

        # Tick 4: Saturated -> streak 4, but within 3600s cooldown -> suppressed
        alert4 = evaluate_cooling_alerts(state, assessment_saturated, now_ts + 90, config)
        self.assertIsNone(alert4)
        self.assertEqual(state.cooling_streak, 4)

        # Tick 5: Normalizes -> healthy -> streak resets to 0
        alert5 = evaluate_cooling_alerts(state, assessment_healthy, now_ts + 120, config)
        self.assertIsNone(alert5)
        self.assertEqual(state.cooling_streak, 0)

    def test_evaluate_cooling_alerts_fan_defect(self):
        class MockState:
            def __init__(self):
                self.cooling_streak = 0
                self.last_cooling_warning_ts = None

        state = MockState()
        now_ts = 1000000.0

        assessment_defect = CoolingAssessment(
            miner_name="S19JPRO-23",
            status=STATUS_FAN_DEFECT,
            status_label="⚠️ DEFECTO FAN",
            max_temp_c=74.0,
            thermal_headroom_c=11.0,
            fan_rpm_max=1200,
            fan_pwm_percent=85.0,
            diagnostic_flags=(),
            recommendation="Defecto",
        )
        config = {
            "cooling_alert_enabled": True,
            "cooling_cooldown_seconds": 3600,
        }

        # Immediate fire without streak delay
        alert1 = evaluate_cooling_alerts(state, assessment_defect, now_ts, config)
        self.assertIsNotNone(alert1)
        self.assertIn("[VENTILADOR]", alert1)
        self.assertIn("1,200 RPM", alert1)
        self.assertEqual(state.last_cooling_warning_ts, now_ts)

        # Immediate repeat within cooldown -> suppressed
        alert2 = evaluate_cooling_alerts(state, assessment_defect, now_ts + 30, config)
        self.assertIsNone(alert2)

    def test_fetch_latest_cooling_assessments_db(self):
        import sqlite3
        import tempfile
        import json
        from pathlib import Path
        from app.fan_health import fetch_latest_cooling_assessments

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
                    max_temp_c REAL,
                    fan_rpm_max INTEGER,
                    fan_pwm_percent REAL,
                    diagnostic_flags_json TEXT
                )
            """)
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, max_temp_c, fan_rpm_max, fan_pwm_percent, diagnostic_flags_json) "
                "VALUES (100.0, '192.168.100.23', 'S19JPRO-23', '192.168.100.23', 'OK', 95.0, 71.5, 5400, 82.0, ?)",
                (json.dumps([]),)
            )
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, max_temp_c, fan_rpm_max, fan_pwm_percent, diagnostic_flags_json) "
                "VALUES (101.0, '192.168.100.24', 'S19JPRO-24', '192.168.100.24', 'OK', 96.0, 79.5, 6300, 98.0, ?)",
                (json.dumps(["high_temperature"]),)
            )
            conn.commit()
            conn.close()

            miners = [
                {"name": "S19JPRO-23", "ip": "192.168.100.23"},
                {"name": "S19JPRO-24", "ip": "192.168.100.24"},
                {"name": "S19JPRO-25", "ip": "192.168.100.25"},  # Not in DB
            ]

            assessments = fetch_latest_cooling_assessments(db_path, miners)
            self.assertEqual(len(assessments), 3)

            # Miner 23: Healthy
            self.assertEqual(assessments[0].miner_name, "S19JPRO-23")
            self.assertEqual(assessments[0].status, STATUS_HEALTHY)
            self.assertEqual(assessments[0].fan_rpm_max, 5400)

            # Miner 24: Saturated
            self.assertEqual(assessments[1].miner_name, "S19JPRO-24")
            self.assertEqual(assessments[1].status, STATUS_SATURATED)
            self.assertEqual(assessments[1].fan_rpm_max, 6300)

            # Miner 25: Unknown
            self.assertEqual(assessments[2].miner_name, "S19JPRO-25")
            self.assertEqual(assessments[2].status, STATUS_UNKNOWN)
        finally:
            if db_path.exists():
                db_path.unlink()


class TestFanHealthIntegration(unittest.TestCase):
    def test_cooling_state_persistence(self):
        import tempfile
        import json
        from pathlib import Path
        from app.miner_monitor import save_state, load_state, MinerState

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            st = MinerState(cooling_streak=3, last_cooling_warning_ts=1700000000.0)
            states = {"192.168.100.23": st}
            save_state(state_file, states, last_update_id=50)

            raw = json.loads(state_file.read_text(encoding="utf-8"))
            miner_data = raw["states"]["192.168.100.23"]
            self.assertEqual(miner_data.get("cooling_streak"), 3)
            self.assertEqual(miner_data.get("last_cooling_warning_ts"), 1700000000.0)

            loaded_states, last_id = load_state(state_file)
            self.assertEqual(last_id, 50)
            loaded_st = loaded_states["192.168.100.23"]
            self.assertEqual(loaded_st.cooling_streak, 3)
            self.assertEqual(loaded_st.last_cooling_warning_ts, 1700000000.0)

    def test_fans_benchmark_on_real_db_if_present(self):
        real_db = Path("data/miner_alerts.db")
        if not real_db.exists():
            return
        import time
        from app.fan_health import fetch_latest_cooling_assessments, build_fans_table_text

        miners = [
            {"name": "S19JPRO-23", "ip": "192.168.100.23"},
            {"name": "S19JPRO-24", "ip": "192.168.100.24"},
            {"name": "S19JPRO-25", "ip": "192.168.100.25"},
            {"name": "S19JPRO-26", "ip": "192.168.100.26"},
        ]
        t0 = time.perf_counter()
        assessments = fetch_latest_cooling_assessments(real_db, miners)
        t_query = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        table = build_fans_table_text(assessments)
        t_format = (time.perf_counter() - t1) * 1000.0

        self.assertLess(t_query, 500.0, f"Query took {t_query:.1f}ms, expected < 500ms")
        self.assertIn("Estado de Enfriamiento", table)
        self.assertEqual(len(assessments), 4)

    def test_fan_mode_rendering_in_table_and_detail(self):
        assessment_manual = assess_miner_cooling(
            miner_name="S19JPRO-23",
            max_temp_c=78.5,
            fan_rpm_max=5800,
            fan_pwm_percent=100.0,
            fan_mode="manual",
        )
        self.assertEqual(assessment_manual.fan_mode, "manual")

        # Table formatting includes [MANUAL]
        table = build_fans_table_text([assessment_manual])
        self.assertIn("[MANUAL]", table)
        self.assertIn("100%", table)

        # Detail formatting includes Modo Control
        detail = build_miner_fan_detail_text(assessment_manual)
        self.assertIn("• Modo Control: MANUAL", detail)
        self.assertIn("• Potencia PWM: 100.0% (MANUAL)", detail)

        # Auto mode test
        assessment_auto = assess_miner_cooling(
            miner_name="S19JPRO-24",
            max_temp_c=72.0,
            fan_rpm_max=4500,
            fan_pwm_percent=70.0,
            fan_mode="auto",
        )
        self.assertEqual(assessment_auto.fan_mode, "auto")
        table_auto = build_fans_table_text([assessment_auto])
        self.assertIn("[AUTO]", table_auto)
        detail_auto = build_miner_fan_detail_text(assessment_auto)
        self.assertIn("• Modo Control: AUTO", detail_auto)


if __name__ == "__main__":
    unittest.main()


