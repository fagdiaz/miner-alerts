import unittest

from app.fan_governor import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_STEP_DOWN,
    ACTION_STEP_UP,
    ACTION_UNKNOWN,
    GovernorConfig,
    compute_governor_step,
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
        # R4: Default floor is 75%
        dec = compute_governor_step(
            max_temp_c=75.0,
            current_duty=75,
            seconds_since_last_change=150.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 75)
        self.assertFalse(dec.requires_write)  # Already at minimum

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

    def test_step_up_when_warm(self):
        # 82.5°C < T < 83.0°C -> step up by 3%
        dec = compute_governor_step(
            max_temp_c=82.7,
            current_duty=84,
            seconds_since_last_change=100.0,
            config=self.cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 87)
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


if __name__ == "__main__":
    unittest.main()
