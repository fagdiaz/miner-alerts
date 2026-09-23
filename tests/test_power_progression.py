"""
Unit tests for Power Progression & Graceful Fallback Orchestrator (PROP-014).
"""

import unittest
from app.governance.power_progression import (
    ACTION_FALLBACK_2500W,
    ACTION_HOLD_FAN_SATURATED,
    ACTION_HOLD_LOCKOUT,
    ACTION_HOLD_SOAK,
    ACTION_HOLD_THERMAL,
    ACTION_NO_ACTION,
    ACTION_PROMOTE_2700W,
    PROFILE_C0_BASE_STABLE,
    PROFILE_C1_ASYMMETRIC,
    PROFILE_C4_MAX_POWER,
    MinerProgressionState,
    ProgressionOrchestratorState,
    evaluate_progression_cycle,
)


class TestPowerProgressionOrchestrator(unittest.TestCase):
    def setUp(self):
        self.state = ProgressionOrchestratorState(
            desired_profile=PROFILE_C4_MAX_POWER,
            current_profile=PROFILE_C0_BASE_STABLE,
            soak_seconds=900.0,
        )
        self.base_telemetry = [
            {"name": "S19JPRO-23", "preset": "2500W", "chip_temp_c": 78.0, "fan_duty_pct": 82.0, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "preset": "2500W", "chip_temp_c": 78.5, "fan_duty_pct": 85.0, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "preset": "2500W", "chip_temp_c": 79.0, "fan_duty_pct": 80.0, "electrical_group": "elevator_2", "max_hardware_preset": "2500W"},
            {"name": "S19JPRO-26", "preset": "2500W", "chip_temp_c": 77.0, "fan_duty_pct": 78.0, "electrical_group": "elevator_2"},
        ]

    def test_promotion_authorized_when_all_gates_pass(self):
        # Initial cycle with clean telemetry and cold chips
        dec = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=1000.0)
        self.assertEqual(dec.action, ACTION_PROMOTE_2700W)
        self.assertEqual(dec.target_miner, "S19JPRO-23")
        self.assertEqual(dec.target_preset, "2700W")
        self.assertIn("Promoción autorizada a 2700W", dec.reason)

    def test_soak_window_blocks_subsequent_promotion(self):
        # First promotion occurs at t=1000s
        dec1 = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=1000.0)
        self.assertEqual(dec1.action, ACTION_PROMOTE_2700W)

        # 300s later (t=1300s), soak window (900s) must hold
        self.base_telemetry[0]["preset"] = "2700W"
        dec2 = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=1300.0)
        self.assertEqual(dec2.action, ACTION_HOLD_SOAK)
        self.assertIn("600s restantes", dec2.reason)

    def test_fan_duty_saturation_blocks_promotion(self):
        # Miner 23 has saturated fans (96% >= 90%)
        self.base_telemetry[0]["fan_duty_pct"] = 96.0
        dec = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=2000.0)
        self.assertEqual(dec.action, ACTION_HOLD_FAN_SATURATED)
        self.assertEqual(dec.target_miner, "S19JPRO-23")
        self.assertIn("Ventiladores saturados al 96%", dec.reason)

    def test_chip_temperature_blocks_promotion(self):
        # Miner 23 has hot chips (81.5°C >= 80.0°C)
        self.base_telemetry[0]["chip_temp_c"] = 81.5
        dec = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=2000.0)
        self.assertEqual(dec.action, ACTION_HOLD_THERMAL)
        self.assertEqual(dec.target_miner, "S19JPRO-23")
        self.assertIn("Chip a 81.5°C", dec.reason)

    def test_immediate_fallback_on_thermal_tripwire(self):
        # Miner 26 is at 2700W and touches 84.0°C (>= 83.5°C)
        self.base_telemetry[3]["preset"] = "2700W"
        self.base_telemetry[3]["chip_temp_c"] = 84.0
        dec = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=3000.0)
        self.assertEqual(dec.action, ACTION_FALLBACK_2500W)
        self.assertEqual(dec.target_miner, "S19JPRO-26")
        self.assertEqual(dec.target_preset, "2500W")
        self.assertIn("Alivio térmico inmediato", dec.reason)

    def test_sustained_thermal_accumulation_triggers_fallback(self):
        # Miner 26 is at 2700W and hovers at 83.2°C for 2 consecutive ticks (60s)
        self.base_telemetry[3]["preset"] = "2700W"
        self.base_telemetry[3]["chip_temp_c"] = 83.2

        # Tick 1: 30s accumulated
        dec1 = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=3000.0)
        self.assertEqual(dec1.action, ACTION_PROMOTE_2700W)  # Fallback hasn't triggered yet

        # Tick 2: 60s reached -> FALLBACK!
        dec2 = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=3030.0)
        self.assertEqual(dec2.action, ACTION_FALLBACK_2500W)
        self.assertEqual(dec2.target_miner, "S19JPRO-26")
        self.assertIn("Alivio térmico acumulado", dec2.reason)

    def test_thermal_lockout_prevents_immediate_re_promotion(self):
        # Miner 26 suffered fallback at t=3000s
        self.base_telemetry[3]["preset"] = "2700W"
        self.base_telemetry[3]["chip_temp_c"] = 84.0
        dec_fb = evaluate_progression_cycle(self.base_telemetry, self.state, now_ts=3000.0)
        self.assertEqual(dec_fb.action, ACTION_FALLBACK_2500W)

        # Soak window passes, chips cool down to 76.0°C, but lockout (1800s) remains active!
        self.state.last_transition_ts = 0.0  # Clear soak for test
        self.base_telemetry[3]["preset"] = "2500W"
        self.base_telemetry[3]["chip_temp_c"] = 76.0

        # At t=3600s (600s post-fallback < 1800s lockout), miner 26 must not be re-promoted
        m26_st = self.state.miner_states["S19JPRO-26"]
        in_lock, rem = m26_st.is_in_lockout(3600.0)
        self.assertTrue(in_lock)
        self.assertEqual(rem, 1200.0)


if __name__ == "__main__":
    unittest.main()
