import unittest

from app.governance.fan_governor import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_RECOVERY_MAX_COOLING,
    ACTION_STEP_DOWN,
    ACTION_STEP_UP,
    ACTION_UNKNOWN,
    GovernorConfig,
    compute_governor_step,
    resolve_power_fan_floor,
)


class TestFanGovernor(unittest.TestCase):
    def setUp(self):
        self.cfg = GovernorConfig()

    def test_unknown_telemetry(self):
        dec = compute_governor_step(
            max_temp_c=None,
            current_duty=100,
            seconds_since_last_change=150.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_UNKNOWN)
        self.assertEqual(dec.target_duty, 100)
        self.assertFalse(dec.requires_write)
        self.assertFalse(dec.is_emergency)

    def test_emergency_spike_override(self):
        # Temp >= 83.0°C triggers immediate spike to 100% even if in dwell
        dec = compute_governor_step(
            max_temp_c=83.2,
            current_duty=85,
            seconds_since_last_change=10.0,  # inside dwell!
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.is_emergency)
        self.assertTrue(dec.requires_write)
        self.assertEqual(dec.dwell_effective, 0)

    def test_emergency_spike_already_100(self):
        # Temp >= 83.0°C but already at 100% -> requires_write is False
        dec = compute_governor_step(
            max_temp_c=83.5,
            current_duty=100,
            seconds_since_last_change=20.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(dec.target_duty, 100)
        self.assertFalse(dec.requires_write)

    def test_failsafe_fault_on_consecutive_failures(self):
        # R3: 3+ failures forces failsafe fault back to 100%
        dec = compute_governor_step(
            max_temp_c=79.0,
            current_duty=80,
            seconds_since_last_change=200.0,
            consecutive_failures=3,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_FAILSAFE_FAULT)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.is_emergency)
        self.assertTrue(dec.requires_write)

    def test_hold_dwell_base(self):
        # Less than 90s since last change
        dec = compute_governor_step(
            max_temp_c=78.0,
            current_duty=90,
            seconds_since_last_change=45.0,
            consecutive_holds=0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_HOLD_DWELL)
        self.assertEqual(dec.target_duty, 90)
        self.assertEqual(dec.dwell_effective, 90)
        self.assertFalse(dec.requires_write)

    def test_adaptive_dwell_extension(self):
        # R1: consecutive_holds >= 3 extends dwell to 120s
        # 100s passed: under base dwell (90s) it would allow step, but adaptive dwell is 120s!
        dec = compute_governor_step(
            max_temp_c=78.0,
            current_duty=90,
            seconds_since_last_change=100.0,
            consecutive_holds=3,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_HOLD_DWELL)
        self.assertEqual(dec.dwell_effective, 120)
        self.assertFalse(dec.requires_write)

    def test_step_down_when_cool(self):
        # T < 81.0°C and dwell expired -> step down by 2%
        dec = compute_governor_step(
            max_temp_c=79.5,
            current_duty=90,
            seconds_since_last_change=95.0,
            consecutive_holds=0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 88)
        self.assertTrue(dec.requires_write)

    def test_minimum_duty_floor(self):
        # Default floor is 30%
        dec = compute_governor_step(
            max_temp_c=75.0,
            current_duty=30,
            seconds_since_last_change=150.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 30)
        self.assertFalse(dec.requires_write)  # Already at minimum

    def test_minimum_duty_floor_custom(self):
        cfg_75 = GovernorConfig(min_fan_duty_percent=75)
        dec = compute_governor_step(
            max_temp_c=75.0,
            current_duty=75,
            seconds_since_last_change=150.0,
            config=cfg_75,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 75)
        self.assertFalse(dec.requires_write)  # Already at custom minimum

    def test_hold_target_deadband(self):
        # 81.0°C <= T <= 82.5°C
        for temp in [81.0, 81.5, 82.0, 82.5]:
            dec = compute_governor_step(
                max_temp_c=temp,
                current_duty=84,
                seconds_since_last_change=100.0,
                config=self.cfg,
            )
            self.assertEqual(dec.action, ACTION_HOLD_TARGET)
            self.assertEqual(dec.target_duty, 84)
            self.assertFalse(dec.requires_write)

    def test_step_up_proportional_urgency_zone(self):
        # 82.5°C < T < 83.0°C with emergency at 83.0°C -> margin 0.3°C <= 0.5°C -> +15%
        dec = compute_governor_step(
            max_temp_c=82.7,
            current_duty=84,
            seconds_since_last_change=100.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 99)  # 84 + 15
        self.assertTrue(dec.requires_write)

    def test_step_up_proportional_alert_zone(self):
        # Margin <= 1.0°C (e.g. emergency at 83.5°C, temp at 82.7°C -> margin 0.8°C) -> +8%
        cfg_alert = GovernorConfig(emergency_spike_temp_c=83.5)
        dec = compute_governor_step(
            max_temp_c=82.7,
            current_duty=84,
            seconds_since_last_change=100.0,
            config=cfg_alert,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 92)  # 84 + 8
        self.assertTrue(dec.requires_write)

    def test_step_up_proportional_standard_zone(self):
        # Margin > 1.0°C (e.g. emergency at 85.0°C, temp at 82.7°C -> margin 2.3°C) -> +3%
        cfg_std = GovernorConfig(emergency_spike_temp_c=85.0)
        dec = compute_governor_step(
            max_temp_c=82.7,
            current_duty=84,
            seconds_since_last_change=100.0,
            config=cfg_std,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 87)  # 84 + 3
        self.assertTrue(dec.requires_write)

    def test_asymmetrical_dwell_bypasses_dwell_on_heating(self):
        # Inside dwell (10s < 90s), but temp 82.7°C > deadband_high_c (82.5°C):
        # Dwell must NOT block step up!
        dec = compute_governor_step(
            max_temp_c=82.7,
            current_duty=84,
            seconds_since_last_change=10.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 99)
        self.assertTrue(dec.requires_write)

    def test_step_up_capped_at_100(self):
        dec = compute_governor_step(
            max_temp_c=82.8,
            current_duty=98,
            seconds_since_last_change=100.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.requires_write)

    def test_recovery_max_cooling_when_below_target_power(self):
        # Even if temp is cool (76.0°C), if current_power is below target by > margin,
        # fans MUST be driven to 100% to let Vnish autoswitch climb up!
        dec = compute_governor_step(
            max_temp_c=76.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=self.cfg,
            current_power_w=2299.0,
            target_power_w=2500.0,
        )
        self.assertEqual(dec.action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.requires_write)

    def test_recovery_max_cooling_already_at_100(self):
        dec = compute_governor_step(
            max_temp_c=76.0,
            current_duty=100,
            seconds_since_last_change=200.0,
            config=self.cfg,
            current_power_w=2299.0,
            target_power_w=2500.0,
        )
        self.assertEqual(dec.action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(dec.target_duty, 100)
        self.assertFalse(dec.requires_write)

    def test_normal_modulation_when_at_target_power(self):
        # When power is at target (e.g. 2480W >= 2500 - 120W), normal thermal modulation applies
        dec = compute_governor_step(
            max_temp_c=79.5,
            current_duty=90,
            seconds_since_last_change=200.0,
            config=self.cfg,
            current_power_w=2480.0,
            target_power_w=2500.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 88)
        self.assertTrue(dec.requires_write)

    def test_step_down_gradient_deep_cold(self):
        # T = 74.0°C (delta = 7.0°C >= 5.0°C): deep cold -> drops by 5% and dwell = 60s
        dec = compute_governor_step(
            max_temp_c=74.0,
            current_duty=90,
            seconds_since_last_change=65.0,
            consecutive_holds=0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 85)
        self.assertEqual(dec.dwell_effective, 60)
        self.assertTrue(dec.requires_write)

    def test_step_down_gradient_moderate_cold(self):
        # T = 77.0°C (delta = 4.0°C >= 2.5°C): moderate cold -> drops by 3%
        dec = compute_governor_step(
            max_temp_c=77.0,
            current_duty=90,
            seconds_since_last_change=95.0,
            consecutive_holds=0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 87)
        self.assertEqual(dec.dwell_effective, 90)
        self.assertTrue(dec.requires_write)

    def test_step_down_gradient_fine_landing(self):
        # T = 79.5°C (delta = 1.5°C < 2.5°C): fine landing approach -> drops by 2%
        dec = compute_governor_step(
            max_temp_c=79.5,
            current_duty=90,
            seconds_since_last_change=95.0,
            consecutive_holds=0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 88)
        self.assertEqual(dec.dwell_effective, 90)
        self.assertTrue(dec.requires_write)

    def test_boost_cooling_headroom_chilling_forces_100_percent(self):
        # T = 81.5°C with duty 90%: inside deadband, but boost_cooling is True -> forces 100% immediately
        dec = compute_governor_step(
            max_temp_c=81.5,
            current_duty=90,
            seconds_since_last_change=10.0,  # inside dwell!
            config=self.cfg,
            boost_cooling=True,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 100)
        self.assertEqual(dec.dwell_effective, 0)
        self.assertTrue(dec.requires_write)
        self.assertIn("Headroom Chilling", dec.reason)

    def test_boost_cooling_suppressed_during_warming_up(self):
        # Even if boost_cooling is requested, warmup floor must be respected
        dec = compute_governor_step(
            max_temp_c=72.0,
            current_duty=50,
            seconds_since_last_change=10.0,
            config=self.cfg,
            is_warming_up=True,
            boost_cooling=True,
        )
        self.assertNotEqual(dec.target_duty, 100)
        self.assertNotIn("Headroom Chilling", dec.reason)

    def test_emergency_spike_overrides_boost_cooling(self):
        # If temp >= 83.0°C, EMERGENCY_SPIKE has absolute priority
        dec = compute_governor_step(
            max_temp_c=83.5,
            current_duty=90,
            seconds_since_last_change=10.0,
            config=self.cfg,
            boost_cooling=True,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_SPIKE)
        self.assertTrue(dec.is_emergency)

    def test_resolve_power_fan_floor(self):
        # 2700W requires 70% min duty
        self.assertEqual(resolve_power_fan_floor(2699.0), 70)
        # 2500W requires 60% min duty
        self.assertEqual(resolve_power_fan_floor(2498.0), 60)
        # 2300W requires 50% min duty
        self.assertEqual(resolve_power_fan_floor(2299.0), 50)
        # 1800W requires 40% min duty
        self.assertEqual(resolve_power_fan_floor(1800.0), 40)
        # Low power / warmup returns 30%
        self.assertEqual(resolve_power_fan_floor(1000.0, is_warming_up=True), 30)
        self.assertEqual(resolve_power_fan_floor(2700.0, is_warming_up=True), 70)
        self.assertEqual(resolve_power_fan_floor(None), 30)

    def test_governor_enforces_power_fan_floor_at_2700w(self):
        # Even if temp is low (60°C), governor must NEVER step down below 70% when drawing 2700W
        dec = compute_governor_step(
            max_temp_c=60.0,
            current_duty=70,
            seconds_since_last_change=150.0,
            config=self.cfg,
            current_power_w=2699.0,
        )
        self.assertEqual(dec.target_duty, 70)
        self.assertFalse(dec.requires_write)

    def test_governor_steps_up_to_power_floor_if_hardware_below(self):
        # If hardware starts at 30% duty while drawing 2700W, governor immediately steps up to 70%
        dec = compute_governor_step(
            max_temp_c=60.0,
            current_duty=30,
            seconds_since_last_change=150.0,
            config=self.cfg,
            current_power_w=2699.0,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 70)
        self.assertTrue(dec.requires_write)

    def test_step_down_strictly_inhibited_during_warmup(self):
        # Critical safety invariant: When a miner is warming up post-reboot,
        # chips are cold (70°C). Governor must NEVER step down fans, preventing
        # thermal surge to 86°C once hashboards reach full power.
        dec = compute_governor_step(
            max_temp_c=70.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=self.cfg,
            is_warming_up=True,
            current_power_w=2499.0,
        )
        self.assertEqual(dec.action, ACTION_HOLD_DWELL)
        self.assertEqual(dec.target_duty, 85)
        self.assertFalse(dec.requires_write)
        self.assertIn("calentamiento post-arranque", dec.reason)

    def test_resolve_power_fan_floor_custom_values(self):
        # Configurable floors: 2700W -> 80%, 2500W -> 75%
        floor_2500 = resolve_power_fan_floor(2498.0, floor_2500w=75)
        self.assertEqual(floor_2500, 75)
        floor_2700 = resolve_power_fan_floor(2700.0, floor_2700w=82)
        self.assertEqual(floor_2700, 82)

    def test_governor_enforces_75_pct_floor_at_2500w(self):
        # With power_floor_2500w=75, governor must never lower fans below 75% at 2500W
        custom_cfg = GovernorConfig(power_floor_2500w=75)
        dec = compute_governor_step(
            max_temp_c=70.0,
            current_duty=75,
            seconds_since_last_change=200.0,
            config=custom_cfg,
            current_power_w=2499.0,
        )
        self.assertEqual(dec.target_duty, 75)
        self.assertFalse(dec.requires_write)

    def test_recovery_max_cooling_active_under_timeout(self):
        # Deficit power triggers RECOVERY_MAX_COOLING while under timeout
        cfg = GovernorConfig(recovery_max_cooling_timeout_seconds=900.0)
        dec = compute_governor_step(
            max_temp_c=77.0,
            current_duty=100,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=2499.0,
            target_power_w=2700.0,
            recovery_cooling_seconds=300.0,
        )
        self.assertEqual(dec.action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(dec.target_duty, 100)

    def test_recovery_max_cooling_times_out_and_modulates_normally(self):
        # After timeout (> 900s) and chip temp <= deadband (77°C <= 81°C),
        # governor exits RECOVERY_MAX_COOLING and steps down towards power floor
        cfg = GovernorConfig(
            recovery_max_cooling_timeout_seconds=900.0,
            power_floor_2700w=85,
        )
        dec = compute_governor_step(
            max_temp_c=77.0,
            current_duty=100,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=2499.0,
            target_power_w=2700.0,
            recovery_cooling_seconds=950.0,
        )
        self.assertNotEqual(dec.action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertTrue(dec.target_duty < 100)
        self.assertGreaterEqual(dec.target_duty, 85)

    def test_recovery_max_cooling_timeout_preserves_emergency_spike(self):
        # Even after timeout, an emergency thermal spike (>= 83°C) forces 100%
        cfg = GovernorConfig(recovery_max_cooling_timeout_seconds=900.0)
        dec = compute_governor_step(
            max_temp_c=83.5,
            current_duty=85,
            seconds_since_last_change=200.0,
            config=cfg,
            current_power_w=2499.0,
            target_power_w=2700.0,
            recovery_cooling_seconds=1200.0,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.requires_write)


if __name__ == "__main__":
    unittest.main()

