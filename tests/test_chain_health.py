"""Unit tests for Predictive Chain Health Assessment Engine (Spec 054)."""

import unittest

from app.governance.chain_health import (
    STATUS_CHAIN_DEFICIT,
    STATUS_CHAIN_FAULT,
    STATUS_CHAIN_OK,
    STATUS_CHAIN_SENSOR_ERROR,
    STATUS_CHAIN_UNKNOWN,
    assess_miner_chains,
    assess_single_chain,
    build_chain_alert_card,
    build_chains_card_text,
    build_chains_fleet_summary_text,
    evaluate_chain_health_streak,
    find_culprit_chain_for_restart,
)
from app.governance.preset_balancer import record_elevator_restart_circumstance
from app.telegram.fleet_cards import build_chains_keyboard, parse_diagnostic_callback
from app.telegram.help_center import HELP_CATEGORIES, lookup_command, visible_line_width
from app.vnish.chains import ChainSensor, ChainTelemetry


class ChainHealthAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.sensor_ok = ChainSensor(state="measure", board_temp=45.0, chip_temp=60.0, loc=28)
        self.sensor_err_28 = ChainSensor(state="error", board_temp=39.0, chip_temp=54.0, loc=28)
        self.sensor_err_99 = ChainSensor(state="error", board_temp=40.0, chip_temp=55.0, loc=99)

        self.healthy_chain = ChainTelemetry(
            chain_id=1,
            state="mining",
            hr_realtime_mhs=33000.0,
            hr_nominal_mhs=33000.0,
            freq_mhz_avg=520.0,
            sensors=[self.sensor_ok],
            sensors_error_count=0,
            chips_total=126,
        )

        self.sensor_fault_chain = ChainTelemetry(
            chain_id=2,
            state="mining",
            hr_realtime_mhs=33500.0,
            hr_nominal_mhs=33500.0,
            freq_mhz_avg=515.0,
            sensors=[self.sensor_err_28],
            sensors_error_count=1,
            chips_total=126,
        )

        self.deficit_chain = ChainTelemetry(
            chain_id=3,
            state="mining",
            hr_realtime_mhs=28000.0,
            hr_nominal_mhs=33000.0,
            freq_mhz_avg=500.0,
            sensors=[self.sensor_ok],
            sensors_error_count=0,
            chips_total=126,
        )

        self.stopped_chain = ChainTelemetry(
            chain_id=1,
            state="stopped",
            hr_realtime_mhs=0.0,
            hr_nominal_mhs=33000.0,
            freq_mhz_avg=0.0,
            sensors=[],
            sensors_error_count=0,
            chips_total=126,
        )

    def test_assess_single_chain_ok(self):
        ass = assess_single_chain("S19JPRO-23", self.healthy_chain)
        self.assertEqual(ass.status, STATUS_CHAIN_OK)
        self.assertTrue(ass.is_healthy)
        self.assertEqual(ass.sensors_error_count, 0)
        self.assertEqual(ass.faulty_sensor_locs, ())

    def test_assess_single_chain_sensor_error(self):
        ass = assess_single_chain("S19JPRO-24", self.sensor_fault_chain)
        self.assertEqual(ass.status, STATUS_CHAIN_SENSOR_ERROR)
        self.assertFalse(ass.is_healthy)
        self.assertEqual(ass.sensors_error_count, 1)
        self.assertEqual(ass.faulty_sensor_locs, (28,))
        self.assertIn("loc 28", ass.recommendation)

    def test_assess_single_chain_deficit(self):
        ass = assess_single_chain("S19JPRO-25", self.deficit_chain)
        self.assertEqual(ass.status, STATUS_CHAIN_DEFICIT)
        self.assertFalse(ass.is_healthy)
        self.assertGreaterEqual(ass.hr_deficit_pct, 10.0)

    def test_assess_single_chain_fault(self):
        ass = assess_single_chain("S19JPRO-26", self.stopped_chain)
        self.assertEqual(ass.status, STATUS_CHAIN_FAULT)
        self.assertFalse(ass.is_healthy)

    def test_assess_single_chain_dict_compatibility(self):
        raw_dict = {
            "chain_id": 2,
            "state": "mining",
            "hr_realtime": 33000.0,
            "hr_nominal": 33000.0,
            "hr_deficit_pct": 0.0,
            "freq_avg": 515.0,
            "sensors_error_count": 1,
            "sensors_json": '[{"state":"error","loc":28}]',
        }
        ass = assess_single_chain("S19JPRO-24", raw_dict)
        self.assertEqual(ass.status, STATUS_CHAIN_SENSOR_ERROR)
        self.assertEqual(ass.faulty_sensor_locs, (28,))

    def test_assess_miner_chains_all_healthy(self):
        miner_ass = assess_miner_chains("S19JPRO-23", [self.healthy_chain, self.healthy_chain])
        self.assertEqual(miner_ass.overall_status, STATUS_CHAIN_OK)
        self.assertTrue(miner_ass.is_all_healthy)
        self.assertFalse(miner_ass.has_sensor_error)
        self.assertEqual(miner_ass.faulty_chains, ())

    def test_assess_miner_chains_with_sensor_error(self):
        miner_ass = assess_miner_chains(
            "S19JPRO-24",
            [self.healthy_chain, self.sensor_fault_chain, self.healthy_chain],
        )
        self.assertEqual(miner_ass.overall_status, STATUS_CHAIN_SENSOR_ERROR)
        self.assertFalse(miner_ass.is_all_healthy)
        self.assertTrue(miner_ass.has_sensor_error)
        self.assertEqual(miner_ass.faulty_chains, (2,))

    def test_find_culprit_chain_for_restart(self):
        culprit = find_culprit_chain_for_restart([self.healthy_chain, self.sensor_fault_chain])
        self.assertIsNotNone(culprit)
        self.assertEqual(culprit["chain_id"], 2)
        self.assertEqual(culprit["faulty_locs"], [28])

        no_culprit = find_culprit_chain_for_restart([self.healthy_chain])
        self.assertIsNone(no_culprit)

    def test_evaluate_chain_health_streak_and_cooldown(self):
        miner_ass = assess_miner_chains("S19JPRO-24", [self.sensor_fault_chain])
        streak_data = {}

        # 1st time: streak=1 < min_streak=2 -> no alert
        alert, card = evaluate_chain_health_streak(streak_data, miner_ass, min_streak=2, now_ts=1000.0)
        self.assertFalse(alert)
        self.assertIsNone(card)
        self.assertEqual(streak_data["fault_streak"], 1)

        # 2nd time: streak=2 >= min_streak=2 -> alert triggers
        alert, card = evaluate_chain_health_streak(streak_data, miner_ass, min_streak=2, now_ts=1010.0)
        self.assertTrue(alert)
        self.assertIsNotNone(card)
        self.assertEqual(streak_data["fault_streak"], 2)
        self.assertEqual(streak_data["last_alert_ts"], 1010.0)

        # 3rd time: within cooldown (100s later < 7200s) -> no alert
        alert, card = evaluate_chain_health_streak(streak_data, miner_ass, min_streak=2, cooldown_s=7200.0, now_ts=1110.0)
        self.assertFalse(alert)
        self.assertIsNone(card)

        # Healthy sample resets streak
        healthy_ass = assess_miner_chains("S19JPRO-24", [self.healthy_chain])
        evaluate_chain_health_streak(streak_data, healthy_ass, min_streak=2, now_ts=1200.0)
        self.assertEqual(streak_data["fault_streak"], 0)

    def test_evaluate_chain_health_sensor_alerts_disabled(self):
        miner_ass = assess_miner_chains("S19JPRO-24", [self.sensor_fault_chain])
        streak_data = {}
        # Sensor alert suppressed when alert_on_sensor_error=False
        alert, card = evaluate_chain_health_streak(
            streak_data,
            miner_ass,
            min_streak=1,
            alert_on_sensor_error=False,
            now_ts=1000.0,
        )
        self.assertFalse(alert)
        self.assertIsNone(card)

        # But physical chain fault STILL alerts even when alert_on_sensor_error=False
        dead_ass = assess_miner_chains("S19JPRO-24", [self.stopped_chain])
        alert_dead, card_dead = evaluate_chain_health_streak(
            streak_data,
            dead_ass,
            min_streak=1,
            alert_on_sensor_error=False,
            now_ts=1010.0,
        )
        self.assertTrue(alert_dead)
        self.assertIsNotNone(card_dead)

    def test_evaluate_chain_health_snoozed(self):
        dead_ass = assess_miner_chains("S19JPRO-24", [self.stopped_chain])
        streak_data = {}
        alert, card = evaluate_chain_health_streak(
            streak_data,
            dead_ass,
            min_streak=1,
            is_snoozed=True,
            now_ts=1000.0,
        )
        self.assertFalse(alert)
        self.assertIsNone(card)

    def test_build_chain_alert_card_format(self):
        miner_ass = assess_miner_chains("S19JPRO-24", [self.sensor_fault_chain])
        card = build_chain_alert_card("S19JPRO-24", miner_ass)
        self.assertIn("ALERTA SALUD DE CADENA", card)
        self.assertIn("S19JPRO-24", card)
        self.assertIn("Cadena 2", card)
        self.assertIn("loc 28", card)

        # Ensure mobile width constraint: all non-empty lines <= 32 chars visible width
        for line in card.split("\n"):
            if line.strip():
                self.assertLessEqual(visible_line_width(line), 32, f"Line too wide: '{line}'")

    def test_record_elevator_restart_circumstance_with_culprit(self):
        miners = [
            {"name": "23", "host": "192.168.100.23", "electrical_group": "elevator_1"},
            {"name": "24", "host": "192.168.100.24", "electrical_group": "elevator_1"},
        ]
        chain_samples = [self.sensor_fault_chain]
        result = record_elevator_restart_circumstance(
            miner_name="24",
            electrical_group="elevator_1",
            miners=miners,
            chain_samples=chain_samples,
        )
        self.assertIn("culprit_chain", result)
        self.assertIsNotNone(result["culprit_chain"])
        self.assertEqual(result["culprit_chain"]["chain_id"], 2)

    def test_build_chains_card_text_mobile_width(self):
        miner_ass = assess_miner_chains("S19JPRO-24", [self.healthy_chain, self.sensor_fault_chain])
        card = build_chains_card_text(miner_ass)
        self.assertIn("SALUD DE CADENAS", card)
        self.assertIn("S19JPRO-24", card)
        self.assertIn("Cadena 1", card)
        self.assertIn("Cadena 2", card)
        self.assertIn("loc 28 ERROR", card)

        for line in card.split("\n"):
            if line.strip():
                self.assertLessEqual(visible_line_width(line), 32, f"Line too wide: '{line}'")

    def test_build_chains_fleet_summary_text_mobile_width(self):
        ass23 = assess_miner_chains("S19JPRO-23", [self.healthy_chain])
        ass24 = assess_miner_chains("S19JPRO-24", [self.sensor_fault_chain])
        summary = build_chains_fleet_summary_text([ass23, ass24])
        self.assertIn("CADENAS: FLOTA ASIC", summary)
        self.assertIn("S19-23", summary)
        self.assertIn("S19-24", summary)
        self.assertIn("loc 28 ERROR", summary)

        for line in summary.split("\n"):
            if line.strip():
                self.assertLessEqual(visible_line_width(line), 32, f"Line too wide: '{line}'")

    def test_build_chains_keyboard_navigation(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
            {"name": "S19JPRO-25", "host": "192.168.100.25"},
        ]
        # Fleet keyboard: has quick-nav buttons for all miners
        kb_fleet = build_chains_keyboard(miners=miners)
        buttons_fleet = [b["text"] for row in kb_fleet["inline_keyboard"] for b in row]
        self.assertIn("🔍 23", buttons_fleet)
        self.assertIn("🔍 24", buttons_fleet)
        self.assertIn("🔍 25", buttons_fleet)
        self.assertIn("🔄 Actualizar Flota", buttons_fleet)

        # Miner-specific keyboard: excludes current miner from jump list
        kb_m24 = build_chains_keyboard(current_miner="24", miners=miners)
        buttons_m24 = [b["text"] for row in kb_m24["inline_keyboard"] for b in row]
        self.assertIn("🔍 23", buttons_m24)
        self.assertNotIn("🔍 24", buttons_m24)
        self.assertIn("🔍 25", buttons_m24)
        self.assertIn("📋 Ver Flota", buttons_m24)

    def test_parse_diagnostic_callback_chains(self):
        # Fleet refresh
        act1 = parse_diagnostic_callback("diag:ref:chains")
        self.assertIsNotNone(act1)
        self.assertEqual(act1.action, "ref")
        self.assertEqual(act1.report_type, "chains")
        self.assertIsNone(act1.miner_id)

        # Miner view
        act2 = parse_diagnostic_callback("diag:chains:24")
        self.assertIsNotNone(act2)
        self.assertEqual(act2.action, "view")
        self.assertEqual(act2.report_type, "chains")
        self.assertEqual(act2.miner_id, "24")

        # Miner refresh
        act3 = parse_diagnostic_callback("diag:ref:chains:24")
        self.assertIsNotNone(act3)
        self.assertEqual(act3.action, "ref")
        self.assertEqual(act3.report_type, "chains")
        self.assertEqual(act3.miner_id, "24")

    def test_help_center_chains_registration(self):
        cmd = lookup_command("chains")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "chains")
        self.assertEqual(cmd.category, "diag")

        alias1 = lookup_command("chain")
        self.assertIsNotNone(alias1)
        self.assertEqual(alias1.name, "chains")

        alias2 = lookup_command("placas")
        self.assertIsNotNone(alias2)
        self.assertEqual(alias2.name, "chains")

        self.assertIn("chains", HELP_CATEGORIES["diag"].command_names)

    def test_uninitialized_sensors_on_failure_chain_no_false_i2c_error(self):
        # When a chain is in 'failure' and sensors are in 'init', do NOT treat as I2C sensor errors
        failure_chain = ChainTelemetry(
            chain_id=1,
            state="failure",
            hr_realtime_mhs=0.0,
            hr_nominal_mhs=0.0,
            freq_mhz_avg=0.0,
            sensors=[
                ChainSensor(state="init", board_temp=0.0, chip_temp=0.0, loc=28),
                ChainSensor(state="init", board_temp=0.0, chip_temp=0.0, loc=61),
                ChainSensor(state="init", board_temp=0.0, chip_temp=0.0, loc=66),
                ChainSensor(state="init", board_temp=0.0, chip_temp=0.0, loc=99),
            ],
            sensors_error_count=0,
        )
        ass = assess_single_chain("S19JPRO-25", failure_chain)
        self.assertEqual(ass.status, STATUS_CHAIN_FAULT)
        self.assertEqual(ass.faulty_sensor_locs, ())
        self.assertEqual(ass.sensors_error_count, 0)

        miner_ass = assess_miner_chains("S19JPRO-25", [failure_chain])
        self.assertFalse(miner_ass.has_sensor_error)
        card = build_chain_alert_card("S19JPRO-25", miner_ass)
        self.assertNotIn("Sensor: loc", card)
        self.assertIn("Cadena fuera de servicio", card)
        for line in card.split("\n"):
            if line.strip():
                self.assertLessEqual(visible_line_width(line), 32, f"Line too wide: '{line}'")


if __name__ == "__main__":
    unittest.main()
