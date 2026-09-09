import unittest
import time
from pathlib import Path
from typing import Optional

from app.vnish.presets import (
    infer_operating_profile,
    assess_miner_preset,
    build_presets_table_text,
    build_miner_preset_detail_text,
    evaluate_preset_alerts,
    fetch_latest_preset_assessments,
    PresetAssessment,
    STATUS_STABLE,
    STATUS_AUTOTUNING,
    STATUS_DOWNCLOCKED,
    STATUS_UNKNOWN,
)


class TestVnishPresets(unittest.TestCase):
    def test_infer_operating_profile(self):
        self.assertEqual(infer_operating_profile(518.0, 2700.0), "~2700W (518 MHz)")
        self.assertEqual(infer_operating_profile(485.0, 2500.0), "~2500W (485 MHz)")
        self.assertEqual(infer_operating_profile(555.0, 3100.0), "~3100W (555 MHz)")
        self.assertEqual(infer_operating_profile(None, None), "Desconocido")

    def test_assess_miner_preset_stable(self):
        assessment = assess_miner_preset(
            miner_name="S19JPRO-24",
            frequency_mhz=518.3,
            voltage_mv=13025.0,
            power_w=2698.0,
            rate_ths=104.5,
            chains_transitioning_count=0,
            baseline_frequency_mhz=518.0,
            recent_events=("Firmware inicio minado",),
        )
        self.assertEqual(assessment.status, STATUS_STABLE)
        self.assertIn("ESTABLE", assessment.status_label)
        self.assertAlmostEqual(assessment.frequency_mhz, 518.3, places=1)
        self.assertAlmostEqual(assessment.voltage_v, 13.03, places=2)
        self.assertIn("sincronía", assessment.recommendation.lower())

    def test_assess_miner_preset_autotuning(self):
        assessment = assess_miner_preset(
            miner_name="S19JPRO-23",
            frequency_mhz=510.0,
            voltage_mv=12800.0,
            power_w=2600.0,
            rate_ths=98.0,
            chains_transitioning_count=1,
            baseline_frequency_mhz=518.0,
            recent_events=("Autotune en progreso (cadena 1)",),
        )
        self.assertEqual(assessment.status, STATUS_AUTOTUNING)
        self.assertIn("AUTOTUNING", assessment.status_label)
        self.assertIn("calibración", assessment.recommendation.lower())

    def test_assess_miner_preset_downclocked(self):
        # Dropped from 518 to 484 MHz (diff 34 MHz >= 25 MHz threshold)
        assessment = assess_miner_preset(
            miner_name="S19JPRO-24",
            frequency_mhz=484.0,
            voltage_mv=12600.0,
            power_w=2490.0,
            rate_ths=93.0,
            chains_transitioning_count=0,
            baseline_frequency_mhz=518.0,
            recent_events=(),
            frequency_drop_threshold_mhz=25.0,
        )
        self.assertEqual(assessment.status, STATUS_DOWNCLOCKED)
        self.assertIn("DOWNCLOCKED", assessment.status_label)
        self.assertIn("redujo", assessment.recommendation.lower())

    def test_assess_miner_preset_unknown(self):
        assessment = assess_miner_preset(
            miner_name="S19JPRO-99",
            frequency_mhz=None,
            voltage_mv=None,
            power_w=None,
            rate_ths=None,
            chains_transitioning_count=0,
            baseline_frequency_mhz=None,
            recent_events=(),
        )
        self.assertEqual(assessment.status, STATUS_UNKNOWN)
        self.assertIn("SIN DATOS", assessment.status_label)

    def test_build_presets_table_text(self):
        assessments = [
            PresetAssessment(
                miner_name="S19JPRO-23",
                status=STATUS_STABLE,
                status_label="🟢 ESTABLE",
                frequency_mhz=516.0,
                voltage_v=12.83,
                power_w=2698.0,
                rate_ths=104.2,
                inferred_profile="~2700W (516 MHz)",
                recent_events=(),
                recommendation="Estable.",
            ),
            PresetAssessment(
                miner_name="S19JPRO-24",
                status=STATUS_DOWNCLOCKED,
                status_label="⚠️ DOWNCLOCKED",
                frequency_mhz=484.9,
                voltage_v=12.89,
                power_w=2499.0,
                rate_ths=94.8,
                inferred_profile="~2500W (485 MHz)",
                recent_events=(),
                recommendation="Perfil reducido.",
            ),
        ]
        text = build_presets_table_text(assessments)
        self.assertIn("Perfiles Operativos y Autotuning", text)
        self.assertIn("S19JPRO-23: 🟢 ESTABLE", text)
        self.assertIn("516.0 MHz", text)
        self.assertIn("12.8V", text)
        self.assertIn("S19JPRO-24: ⚠️ DOWNCLOCKED", text)
        self.assertIn("484.9 MHz", text)
        self.assertIn("/presets <minero>", text)

    def test_build_miner_preset_detail_text(self):
        assessment = PresetAssessment(
            miner_name="S19JPRO-24",
            status=STATUS_STABLE,
            status_label="🟢 ESTABLE",
            frequency_mhz=518.3,
            voltage_v=13.03,
            power_w=2698.0,
            rate_ths=104.5,
            inferred_profile="~2700W (518 MHz)",
            recent_events=("Firmware inicio minado",),
            recommendation="Frecuencia y tensión en sincronía con el perfil nominal.",
        )
        text = build_miner_preset_detail_text(assessment)
        self.assertIn("Diagnóstico de Perfil y Tuning — S19JPRO-24", text)
        self.assertIn("• Estado: 🟢 ESTABLE", text)
        self.assertIn("518.3 MHz", text)
        self.assertIn("13.03 V", text)
        self.assertIn("2,698 W", text)
        self.assertIn("Firmware inicio minado", text)

    def test_evaluate_preset_alerts(self):
        class MockState:
            def __init__(self):
                self.baseline_frequency_mhz = 518.0
                self.last_preset_warning_ts = None

        state = MockState()
        now_ts = 1000000.0

        assessment_downclocked = PresetAssessment(
            miner_name="S19JPRO-24",
            status=STATUS_DOWNCLOCKED,
            status_label="⚠️ DOWNCLOCKED",
            frequency_mhz=484.9,
            voltage_v=12.89,
            power_w=2499.0,
            rate_ths=94.8,
            inferred_profile="~2500W (485 MHz)",
            recent_events=(),
            recommendation="Perfil reducido.",
        )

        config = {
            "preset_alert_enabled": True,
            "preset_cooldown_seconds": 3600,
        }

        # Alert fires on downclock
        alert1 = evaluate_preset_alerts(state, assessment_downclocked, now_ts, config)
        self.assertIsNotNone(alert1)
        self.assertIn("[PERFIL/AUTOTUNE]", alert1)
        self.assertIn("S19JPRO-24", alert1)
        self.assertIn("484.9 MHz", alert1)
        self.assertEqual(state.last_preset_warning_ts, now_ts)

        # Immediate repeat -> cooldown suppresses
        alert2 = evaluate_preset_alerts(state, assessment_downclocked, now_ts + 60, config)
        self.assertIsNone(alert2)

    def test_fetch_latest_preset_assessments_db(self):
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
                    frequency_mhz_avg REAL,
                    chain_voltage_mv_avg REAL,
                    chain_power_w_total REAL,
                    chains_transitioning_count INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE firmware_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_ts REAL NOT NULL,
                    miner_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    code TEXT NOT NULL,
                    summary TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, frequency_mhz_avg, chain_voltage_mv_avg, chain_power_w_total, chains_transitioning_count) "
                "VALUES (100.0, '192.168.100.23', 'S19JPRO-23', '192.168.100.23', 'OK', 104.0, 516.0, 12830.0, 2698.0, 0)"
            )
            conn.execute(
                "INSERT INTO telemetry_samples (observed_ts, miner_key, miner_name, host, state, rate_ths, frequency_mhz_avg, chain_voltage_mv_avg, chain_power_w_total, chains_transitioning_count) "
                "VALUES (101.0, '192.168.100.24', 'S19JPRO-24', '192.168.100.24', 'OK', 95.0, 485.0, 12600.0, 2498.0, 0)"
            )
            conn.commit()
            conn.close()

            miners = [
                {"name": "S19JPRO-23", "ip": "192.168.100.23"},
                {"name": "S19JPRO-24", "ip": "192.168.100.24"},
                {"name": "S19JPRO-25", "ip": "192.168.100.25"},
            ]

            assessments = fetch_latest_preset_assessments(db_path, miners)
            self.assertEqual(len(assessments), 3)

            # Miner 23: 516 MHz
            self.assertEqual(assessments[0].miner_name, "S19JPRO-23")
            self.assertAlmostEqual(assessments[0].frequency_mhz, 516.0, places=1)

            # Miner 24: 485 MHz
            self.assertEqual(assessments[1].miner_name, "S19JPRO-24")
            self.assertAlmostEqual(assessments[1].frequency_mhz, 485.0, places=1)

            # Miner 25: Unknown
            self.assertEqual(assessments[2].miner_name, "S19JPRO-25")
            self.assertEqual(assessments[2].status, STATUS_UNKNOWN)
        finally:
            if db_path.exists():
                db_path.unlink()


class TestVnishPresetsIntegration(unittest.TestCase):
    def test_preset_state_persistence(self):
        import tempfile
        import json
        from pathlib import Path
        from app.miner_monitor import save_state, load_state, MinerState

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            st = MinerState(baseline_frequency_mhz=518.0, last_preset_warning_ts=1700000000.0)
            states = {"192.168.100.23": st}
            save_state(state_file, states, last_update_id=60)

            raw = json.loads(state_file.read_text(encoding="utf-8"))
            miner_data = raw["states"]["192.168.100.23"]
            self.assertEqual(miner_data.get("baseline_frequency_mhz"), 518.0)
            self.assertEqual(miner_data.get("last_preset_warning_ts"), 1700000000.0)

            loaded_states, last_id = load_state(state_file)
            self.assertEqual(last_id, 60)
            loaded_st = loaded_states["192.168.100.23"]
            self.assertEqual(loaded_st.baseline_frequency_mhz, 518.0)
            self.assertEqual(loaded_st.last_preset_warning_ts, 1700000000.0)

    def test_presets_benchmark_on_real_db_if_present(self):
        real_db = Path("data/miner_alerts.db")
        if not real_db.exists():
            return
        import time
        from app.vnish.presets import fetch_latest_preset_assessments, build_presets_table_text

        miners = [
            {"name": "S19JPRO-23", "ip": "192.168.100.23"},
            {"name": "S19JPRO-24", "ip": "192.168.100.24"},
            {"name": "S19JPRO-25", "ip": "192.168.100.25"},
            {"name": "S19JPRO-26", "ip": "192.168.100.26"},
        ]
        t0 = time.perf_counter()
        assessments = fetch_latest_preset_assessments(real_db, miners)
        t_query = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        table = build_presets_table_text(assessments)
        t_format = (time.perf_counter() - t1) * 1000.0

        self.assertLess(t_query, 500.0, f"Query took {t_query:.1f}ms, expected < 500ms")
        self.assertIn("Perfiles Operativos y Autotuning", table)
        self.assertEqual(len(assessments), 4)


if __name__ == "__main__":
    unittest.main()
