"""
Unit and integration tests for Spec 063 — Gobernador Térmico con Conciencia Estacional
(Ambient-Aware Thermal PID — GOV-02).
"""

import threading
import unittest
from app.governance.fan_governor import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_STEP_DOWN,
    ACTION_STEP_UP,
    ACTION_UNKNOWN,
    SEASONAL_MODE_STANDARD,
    SEASONAL_MODE_SUMMER,
    SEASONAL_MODE_WINTER,
    GovernorConfig,
    compute_governor_step,
    resolve_seasonal_parameters,
)
from app.miner_monitor import MinerState, execute_governor_cycle
from app.vnish.telemetry import VnishTelemetry, normalize_vnish_stats


class TestSeasonalGovernorResolution(unittest.TestCase):
    """Verify resolve_seasonal_parameters() for winter, standard, and summer modes."""

    def setUp(self) -> None:
        self.cfg = GovernorConfig()

    def test_winter_mode_threshold(self) -> None:
        # T_amb < 18.0°C triggers Winter Mode
        res = resolve_seasonal_parameters(12.0, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_WINTER)
        self.assertEqual(res.target_temp_c, 76.0)
        self.assertEqual(res.deadband_low_c, 75.0)
        self.assertEqual(res.deadband_high_c, 77.0)
        self.assertEqual(res.min_duty_percent, 45)
        self.assertEqual(res.step_up_percent, 3)

    def test_winter_mode_boundary(self) -> None:
        # Just below 18.0°C (17.99°C) is Winter
        res = resolve_seasonal_parameters(17.99, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_WINTER)

    def test_standard_mode_lower_boundary(self) -> None:
        # Exactly 18.0°C is Standard
        res = resolve_seasonal_parameters(18.0, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_STANDARD)
        self.assertEqual(res.target_temp_c, 82.0)
        self.assertEqual(res.deadband_low_c, 81.0)
        self.assertEqual(res.deadband_high_c, 82.5)
        self.assertEqual(res.min_duty_percent, 30)
        self.assertEqual(res.step_up_percent, 3)

    def test_standard_mode_upper_boundary(self) -> None:
        # Exactly 28.0°C is Standard
        res = resolve_seasonal_parameters(28.0, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_STANDARD)
        self.assertEqual(res.target_temp_c, 82.0)
        self.assertEqual(res.deadband_low_c, 81.0)
        self.assertEqual(res.deadband_high_c, 82.5)

    def test_summer_mode_threshold(self) -> None:
        # T_amb > 28.0°C triggers Summer Mode
        res = resolve_seasonal_parameters(32.5, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_SUMMER)
        self.assertEqual(res.target_temp_c, 80.0)
        self.assertEqual(res.deadband_low_c, 79.0)
        self.assertEqual(res.deadband_high_c, 81.0)
        self.assertEqual(res.min_duty_percent, 65)
        self.assertEqual(res.step_up_percent, 5)

    def test_summer_mode_boundary(self) -> None:
        # Just above 28.0°C (28.01°C) is Summer
        res = resolve_seasonal_parameters(28.01, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_SUMMER)

    def test_missing_ambient_telemetry_fallback(self) -> None:
        # None ambient temperature must fall back to Standard mode
        res = resolve_seasonal_parameters(None, self.cfg)
        self.assertEqual(res.mode, SEASONAL_MODE_STANDARD)
        self.assertIsNone(res.ambient_temp_c)
        self.assertEqual(res.target_temp_c, 82.0)
        self.assertEqual(res.min_duty_percent, 30)

    def test_seasonal_disabled_fallback(self) -> None:
        # seasonal_enabled = False must fall back to Standard mode even at 5°C or 35°C
        cfg_disabled = GovernorConfig(seasonal_enabled=False)
        res_winter = resolve_seasonal_parameters(5.0, cfg_disabled)
        self.assertEqual(res_winter.mode, SEASONAL_MODE_STANDARD)
        self.assertEqual(res_winter.target_temp_c, 82.0)

        res_summer = resolve_seasonal_parameters(35.0, cfg_disabled)
        self.assertEqual(res_summer.mode, SEASONAL_MODE_STANDARD)
        self.assertEqual(res_summer.target_temp_c, 82.0)

    def test_invalid_sensor_readings_fallback(self) -> None:
        # Extreme/corrupt readings outside [-10.0, 60.0]°C fall back to Standard
        res_hot = resolve_seasonal_parameters(120.0, self.cfg)
        self.assertEqual(res_hot.mode, SEASONAL_MODE_STANDARD)
        self.assertIsNone(res_hot.ambient_temp_c)

        res_cold = resolve_seasonal_parameters(-40.0, self.cfg)
        self.assertEqual(res_cold.mode, SEASONAL_MODE_STANDARD)
        self.assertIsNone(res_cold.ambient_temp_c)

    def test_sensor_validity_bounds(self) -> None:
        # Exact valid extremes: -10.0°C is Winter, 60.0°C is Summer
        res_neg = resolve_seasonal_parameters(-10.0, self.cfg)
        self.assertEqual(res_neg.mode, SEASONAL_MODE_WINTER)
        self.assertEqual(res_neg.ambient_temp_c, -10.0)

        res_pos = resolve_seasonal_parameters(60.0, self.cfg)
        self.assertEqual(res_pos.mode, SEASONAL_MODE_SUMMER)
        self.assertEqual(res_pos.ambient_temp_c, 60.0)

        # Barely out of range
        res_below = resolve_seasonal_parameters(-10.1, self.cfg)
        self.assertEqual(res_below.mode, SEASONAL_MODE_STANDARD)
        self.assertIsNone(res_below.ambient_temp_c)

        res_above = resolve_seasonal_parameters(60.1, self.cfg)
        self.assertEqual(res_above.mode, SEASONAL_MODE_STANDARD)
        self.assertIsNone(res_above.ambient_temp_c)


class TestInviolableSafetyInvariants(unittest.TestCase):
    """Verify that the 3 inviolable safety invariants cannot be breached under any configuration."""

    def test_invariant_1_target_temp_cannot_exceed_82c(self) -> None:
        # Invariant 1: effective_target_temp_c <= 82.0°C
        bad_cfg = GovernorConfig(
            target_temp_c=88.0,
            winter_target_temp_c=85.0,
            summer_target_temp_c=89.0,
        )
        # Winter mode target clamped to 82.0°C
        res_w = resolve_seasonal_parameters(10.0, bad_cfg)
        self.assertLessEqual(res_w.target_temp_c, 82.0)
        self.assertLessEqual(res_w.deadband_high_c, 82.5)

        # Summer mode target clamped to 82.0°C
        res_s = resolve_seasonal_parameters(35.0, bad_cfg)
        self.assertLessEqual(res_s.target_temp_c, 82.0)
        self.assertLessEqual(res_s.deadband_high_c, 82.5)

        # Standard mode target clamped to 82.0°C
        res_std = resolve_seasonal_parameters(22.0, bad_cfg)
        self.assertLessEqual(res_std.target_temp_c, 82.0)
        self.assertLessEqual(res_std.deadband_high_c, 82.5)

    def test_invariant_2_min_duty_cannot_drop_below_30_percent(self) -> None:
        # Invariant 2: effective_min_duty_percent >= 30%
        bad_cfg = GovernorConfig(
            min_fan_duty_percent=10,
            winter_min_duty_percent=15,
            summer_min_duty_percent=20,
        )
        res_w = resolve_seasonal_parameters(10.0, bad_cfg)
        self.assertGreaterEqual(res_w.min_duty_percent, 30)

        res_s = resolve_seasonal_parameters(35.0, bad_cfg)
        self.assertGreaterEqual(res_s.min_duty_percent, 30)

        res_std = resolve_seasonal_parameters(22.0, bad_cfg)
        self.assertGreaterEqual(res_std.min_duty_percent, 30)

    def test_invariant_3_emergency_thermal_spike_inviolable(self) -> None:
        # Invariant 3: Emergency thermal spike (T >= 83.0°C) overrides all modes to 100% PWM
        cfg = GovernorConfig(emergency_spike_temp_c=83.0)

        # Winter mode, inside dwell, currently at 45%: chip at 83.5°C triggers immediate 100%
        dec_w = compute_governor_step(
            max_temp_c=83.5,
            current_duty=45,
            seconds_since_last_change=10.0,
            config=cfg,
            ambient_temp_c=5.0,
        )
        self.assertEqual(dec_w.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(dec_w.target_duty, 100)
        self.assertTrue(dec_w.is_emergency)
        self.assertTrue(dec_w.requires_write)
        self.assertEqual(dec_w.seasonal_mode, SEASONAL_MODE_WINTER)

        # Summer mode, inside dwell: chip at 85.0°C triggers immediate 100%
        dec_s = compute_governor_step(
            max_temp_c=85.0,
            current_duty=70,
            seconds_since_last_change=5.0,
            config=cfg,
            ambient_temp_c=35.0,
        )
        self.assertEqual(dec_s.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(dec_s.target_duty, 100)
        self.assertTrue(dec_s.is_emergency)
        self.assertEqual(dec_s.seasonal_mode, SEASONAL_MODE_SUMMER)


class TestComputeGovernorStepSeasonal(unittest.TestCase):
    """Test compute_governor_step behavior with winter, standard, and summer profiles."""

    def setUp(self) -> None:
        self.cfg = GovernorConfig()

    def test_winter_hold_target(self) -> None:
        # In winter (10°C), deadband is [75.0, 77.0]°C. Chip at 76.0°C holds target
        dec = compute_governor_step(
            max_temp_c=76.0,
            current_duty=50,
            seconds_since_last_change=150.0,
            config=self.cfg,
            ambient_temp_c=10.0,
        )
        self.assertEqual(dec.action, ACTION_HOLD_TARGET)
        self.assertEqual(dec.target_duty, 50)
        self.assertFalse(dec.requires_write)
        self.assertEqual(dec.seasonal_mode, SEASONAL_MODE_WINTER)

    def test_winter_step_up_above_77c(self) -> None:
        # In winter (10°C), chip at 78.0°C (> 77.0°C) steps up
        dec = compute_governor_step(
            max_temp_c=78.0,
            current_duty=50,
            seconds_since_last_change=150.0,
            config=self.cfg,
            ambient_temp_c=10.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 53)  # 50 + 3% step_up
        self.assertTrue(dec.requires_write)
        self.assertEqual(dec.seasonal_mode, SEASONAL_MODE_WINTER)

    def test_winter_step_down_bounded_by_floor(self) -> None:
        # In winter, min duty floor is 45%. If current duty is 46% and chip is cool (72°C),
        # step down (-3%) is clamped at 45%
        dec = compute_governor_step(
            max_temp_c=72.0,
            current_duty=46,
            seconds_since_last_change=150.0,
            config=self.cfg,
            ambient_temp_c=10.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 45)  # Clamped at 45% floor
        self.assertTrue(dec.requires_write)

    def test_winter_enforces_floor_from_standard_duty(self) -> None:
        # If miner is currently at 30% PWM and winter mode requires 45% floor,
        # immediate step up to 45% floor must occur
        dec = compute_governor_step(
            max_temp_c=70.0,
            current_duty=30,
            seconds_since_last_change=10.0,
            config=self.cfg,
            ambient_temp_c=10.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 45)
        self.assertTrue(dec.requires_write)

    def test_summer_hold_target(self) -> None:
        # In summer (32°C), deadband is [79.0, 81.0]°C. Chip at 80.0°C holds target
        dec = compute_governor_step(
            max_temp_c=80.0,
            current_duty=70,
            seconds_since_last_change=150.0,
            config=self.cfg,
            ambient_temp_c=32.0,
        )
        self.assertEqual(dec.action, ACTION_HOLD_TARGET)
        self.assertEqual(dec.target_duty, 70)
        self.assertFalse(dec.requires_write)
        self.assertEqual(dec.seasonal_mode, SEASONAL_MODE_SUMMER)

    def test_summer_accelerated_step_up_above_81c(self) -> None:
        # In summer (32°C), chip at 81.5°C (> 81.0°C) triggers accelerated step up (+5%)
        dec = compute_governor_step(
            max_temp_c=81.5,
            current_duty=70,
            seconds_since_last_change=150.0,
            config=self.cfg,
            ambient_temp_c=32.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 75)  # 70 + 5% accelerated step_up
        self.assertTrue(dec.requires_write)
        self.assertEqual(dec.seasonal_mode, SEASONAL_MODE_SUMMER)

    def test_summer_enforces_floor_from_standard_duty(self) -> None:
        # In summer, floor is 65%. If current duty is 50%, immediately step up to 65%
        dec = compute_governor_step(
            max_temp_c=75.0,
            current_duty=50,
            seconds_since_last_change=10.0,
            config=self.cfg,
            ambient_temp_c=32.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 65)
        self.assertTrue(dec.requires_write)

    def test_summer_silent_mode_precedence(self) -> None:
        # Silent Mode sets max_fan_duty_percent = 50% (acoustic ceiling).
        # In summer, normal min duty is 65%.
        # Defensive clamp ensures effective floor <= ceiling (50%) without oscillation
        cfg_silent = GovernorConfig(max_fan_duty_percent=50)
        dec = compute_governor_step(
            max_temp_c=78.0,
            current_duty=50,
            seconds_since_last_change=150.0,
            config=cfg_silent,
            ambient_temp_c=32.0,
        )
        # Holds target or steps down within 50% ceiling
        self.assertLessEqual(dec.target_duty, 50)


class TestTelemetryInletExtraction(unittest.TestCase):
    """Test inlet temperature extraction from Vnish stats payloads."""

    def test_extracts_inlet_from_temp_in(self) -> None:
        payload = {
            "STATS": [
                {},
                {
                    "temp_chip1": 78.0,
                    "temp_in": 16.5,
                    "fan1": 5500,
                    "chain_vol1": 12800,
                },
            ]
        }
        telemetry = normalize_vnish_stats(payload)
        self.assertEqual(telemetry.max_temp_c, 78.0)
        self.assertEqual(telemetry.inlet_temp_c, 16.5)
        self.assertEqual(telemetry.as_dict()["inlet_temp_c"], 16.5)

    def test_averages_multiple_inlet_sensors(self) -> None:
        payload = {
            "STATS": [
                {},
                {
                    "temp_chip1": 75.0,
                    "temp_pcb_in1": 14.0,
                    "temp_pcb_in2": 16.0,
                    "fan1": 5000,
                },
            ]
        }
        telemetry = normalize_vnish_stats(payload)
        self.assertEqual(telemetry.inlet_temp_c, 15.0)

    def test_discards_anomalous_inlet_temperatures(self) -> None:
        # Inlets > 60°C or < -10°C are rejected
        payload = {
            "STATS": [
                {},
                {
                    "temp_chip1": 75.0,
                    "temp_in1": 120.0,  # Corrupt
                    "temp_in2": 22.0,   # Valid
                    "fan1": 5000,
                },
            ]
        }
        telemetry = normalize_vnish_stats(payload)
        self.assertEqual(telemetry.inlet_temp_c, 22.0)

    def test_inlet_temp_missing_when_no_sensor(self) -> None:
        payload = {
            "STATS": [
                {},
                {
                    "temp_chip1": 75.0,
                    "temp_pcb1": 60.0,
                    "fan1": 5000,
                },
            ]
        }
        telemetry = normalize_vnish_stats(payload)
        self.assertIsNone(telemetry.inlet_temp_c)


class TestExecuteGovernorCycleIntegration(unittest.TestCase):
    """Test group-based ambient temperature aggregation in execute_governor_cycle()."""

    def test_group_aggregation_and_seasonal_dispatch(self) -> None:
        state_lock = threading.Lock()
        config = {
            "fan_governor_enabled": True,
            "fan_governor_dry_run": True,
            "fan_governor_target_power_w": 2700.0,
        }

        miners = [
            {
                "name": "S19JPRO-1",
                "host": "192.168.1.101",
                "port": 4028,
                "electrical_group": "elevator_1",
            },
            {
                "name": "S19JPRO-2",
                "host": "192.168.1.102",
                "port": 4028,
                "electrical_group": "elevator_1",
            },
            {
                "name": "S19JPRO-3",
                "host": "192.168.1.103",
                "port": 4028,
                "electrical_group": "elevator_2",
            },
        ]

        st1 = MinerState(governor_duty=50, governor_last_change_ts=0.0)
        st1.governor_last_temp_c = 76.0
        st1.inlet_temp_c = 12.0  # Cold elevator_1

        # st2 has no sensor, but belongs to elevator_1, should inherit group average (12°C)
        st2 = MinerState(governor_duty=50, governor_last_change_ts=0.0)
        st2.governor_last_temp_c = 76.0
        st2.inlet_temp_c = None

        # st3 belongs to elevator_2, is hot (32°C)
        st3 = MinerState(governor_duty=70, governor_last_change_ts=0.0)
        st3.governor_last_temp_c = 80.0
        st3.inlet_temp_c = 32.0  # Warm elevator_2

        states = {
            "S19JPRO-1|192.168.1.101:4028": st1,
            "S19JPRO-2|192.168.1.102:4028": st2,
            "S19JPRO-3|192.168.1.103:4028": st3,
        }

        now_ts = 200.0
        execute_governor_cycle(miners, states, state_lock, config, now_ts)

        # Miner 1 (elevator_1) operated under Winter mode: chip 76°C is inside [75, 77] -> HOLD_TARGET
        self.assertEqual(st1.governor_last_action, ACTION_HOLD_TARGET)

        # Miner 2 (elevator_1) inherited 12°C: chip 76°C is inside [75, 77] -> HOLD_TARGET
        self.assertEqual(st2.governor_last_action, ACTION_HOLD_TARGET)

        # Miner 3 (elevator_2) operated under Summer mode: chip 80°C is inside [79, 81] -> HOLD_TARGET
        self.assertEqual(st3.governor_last_action, ACTION_HOLD_TARGET)


if __name__ == "__main__":
    unittest.main()
