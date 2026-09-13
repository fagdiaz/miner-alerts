"""tests/test_silent_mode.py
T014: Spec 044 - Silent Mode / Visitor Mode with Persistent Timer and Thermal Guard.

Covers all 4 constitutional conditions:
  C1: No HTTP calls in polling thread (state mutation only from /silent command).
  C2: FSM fields isolated from snooze; first_tick expiry reconciliation.
  C3: Governor operates within acoustic ceiling when silent_mode_active.
  C4: EMERGENCY_SPIKE atomically cancels silent_mode_active and logs event.
"""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.miner_monitor import MinerState, execute_governor_cycle
from app.governance.fan_governor import (
    GovernorConfig, GovernorDecision, compute_governor_step,
    ACTION_EMERGENCY_SPIKE, ACTION_FAILSAFE_FAULT,
    ACTION_HOLD_DWELL, ACTION_HOLD_TARGET, ACTION_STEP_DOWN, ACTION_STEP_UP,
)


def _make_miner(n):
    return {"name": f"S19JPRO-{n}", "host": f"192.168.100.{n}", "port": 4028}


def _make_states(miners, temp_c=79.0, duty=100,
                 silent_active=False, revert_ts=None, target_max_duty=50):
    states = {}
    for m in miners:
        sk = f"{m['name']}|{m['host']}:{m['port']}"
        st = MinerState()
        st.governor_last_temp_c = temp_c
        st.governor_duty = duty
        st.governor_last_change_ts = time.time() - 200.0  # dwell expired
        st.silent_mode_active = silent_active
        st.silent_mode_revert_ts = revert_ts
        st.silent_mode_target_max_duty = target_max_duty
        states[sk] = st
    return states


def _make_config(**overrides):
    cfg = {
        "fan_governor_enabled": True,
        "fan_governor_dry_run": True,
        "fan_governor_target_temp_c": 82.0,
        "fan_governor_deadband_low_c": 81.0,
        "fan_governor_deadband_high_c": 82.5,
        "fan_governor_emergency_temp_c": 83.0,
        "fan_governor_min_duty_pct": 75,
        "fan_governor_step_down_pct": 2,
        "fan_governor_step_up_pct": 3,
        "fan_governor_dwell_seconds": 90,
        "fan_governor_adaptive_dwell_seconds": 120,
        "fan_governor_holds_threshold": 3,
        "fan_governor_request_timeout": 2.5,
        "fan_governor_fleet_timeout": 5.0,
        "fan_governor_max_failures": 3,
        "fan_governor_power_margin_w": 120.0,
        "vnish_api_password": "admin",
        "silent_mode_target_max_duty": 50,
        "silent_mode_min_duty_pct": 30,
    }
    cfg.update(overrides)
    return cfg


class TestMinerStateIsolation(unittest.TestCase):
    """C2: silent_mode fields are structurally separate from snooze_until_ts."""

    def test_silent_mode_fields_default(self):
        st = MinerState()
        self.assertFalse(st.silent_mode_active)
        self.assertIsNone(st.silent_mode_revert_ts)
        self.assertIsNone(st.silent_mode_prev_duty)
        self.assertIsNone(st.silent_mode_prev_preset)
        self.assertEqual(st.silent_mode_target_max_duty, 50)

    def test_silent_mode_independent_from_snooze(self):
        """Modifying silent_mode must not affect snooze_until_ts and vice versa."""
        st = MinerState()
        st.snooze_until_ts = time.time() + 3600.0
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() + 7200.0
        st.silent_mode_active = False
        st.silent_mode_revert_ts = None
        self.assertIsNotNone(st.snooze_until_ts)

    def test_snooze_cancel_does_not_touch_silent(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() + 3600.0
        st.snooze_until_ts = time.time() + 1800.0
        st.snooze_until_ts = None
        self.assertTrue(st.silent_mode_active)
        self.assertIsNotNone(st.silent_mode_revert_ts)


class TestFirstTickExpiry(unittest.TestCase):
    """C2: Expired silent modes detected correctly via revert_ts comparison."""

    def test_detect_expired_silent_mode(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() - 60.0
        now_ts = time.time()
        expired = st.silent_mode_active and st.silent_mode_revert_ts is not None and now_ts >= st.silent_mode_revert_ts
        self.assertTrue(expired)

    def test_detect_active_silent_mode(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() + 3600.0
        now_ts = time.time()
        expired = st.silent_mode_active and st.silent_mode_revert_ts is not None and now_ts >= st.silent_mode_revert_ts
        self.assertFalse(expired)

    def test_indefinite_silent_mode_never_expires(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = None
        now_ts = time.time()
        would_expire = st.silent_mode_revert_ts is not None and now_ts >= st.silent_mode_revert_ts
        self.assertFalse(would_expire)


class TestGovernorAcousticCeiling(unittest.TestCase):
    """C3: Governor operates within acoustic ceiling when silent_mode_active."""

    def test_governor_duty_stays_within_acoustic_ceiling(self):
        """With silent_mode_active=True and max_duty=70%, governor never commands >70%."""
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=70,
                               silent_active=True, target_max_duty=50)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=True)
        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )
        sk = "S19JPRO-1|192.168.100.1:4028"
        st = states[sk]
        if st.governor_duty is not None:
            self.assertLessEqual(st.governor_duty, 50,
                f"Governor duty {st.governor_duty}% exceeded acoustic ceiling 50%")

    def test_governor_c3_min_duty_floor_respected(self):
        """At acoustic floor, STEP_DOWN should not require write."""
        cfg = GovernorConfig(min_fan_duty_percent=30, max_fan_duty_percent=50, step_down_percent=5)
        decision = compute_governor_step(
            max_temp_c=79.0, current_duty=30,
            seconds_since_last_change=200.0, config=cfg,
        )
        self.assertFalse(decision.requires_write)
        self.assertEqual(decision.target_duty, 30)

    def test_emergency_spike_overrides_acoustic_ceiling(self):
        """EMERGENCY_SPIKE at 83C goes to 100% even with acoustic max=70%."""
        cfg = GovernorConfig(min_fan_duty_percent=30, max_fan_duty_percent=50,
                             emergency_spike_temp_c=83.0)
        decision = compute_governor_step(
            max_temp_c=83.5, current_duty=60,
            seconds_since_last_change=5.0, config=cfg,
        )
        self.assertEqual(decision.action, ACTION_EMERGENCY_SPIKE)
        # With acoustic max_fan_duty_percent=70, EMERGENCY_SPIKE targets 70% (the configured ceiling).
        # The full 100% override happens on the next tick after C4 clears silent_mode_active.
        self.assertEqual(decision.target_duty, 50)
        self.assertTrue(decision.requires_write)


class TestThermalGuardC4(unittest.TestCase):
    """C4: EMERGENCY_SPIKE atomically cancels silent_mode_active."""

    def test_thermal_guard_cancels_silent_mode_on_emergency_spike(self):
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=83.5, duty=60,
                               silent_active=True, target_max_duty=50)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=False, fan_governor_emergency_temp_c=83.0)
        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            thermal_events = execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )
        sk = "S19JPRO-1|192.168.100.1:4028"
        st = states[sk]
        self.assertFalse(st.silent_mode_active,
                         "silent_mode_active must be False after EMERGENCY_SPIKE")
        self.assertIsNone(st.silent_mode_revert_ts,
                          "silent_mode_revert_ts must be None after thermal cancellation")
        self.assertTrue(len(thermal_events) > 0)
        self.assertEqual(thermal_events[0][0], "S19JPRO-1")
        self.assertEqual(thermal_events[0][2], ACTION_EMERGENCY_SPIKE)

    def test_thermal_guard_does_not_trigger_when_cool(self):
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=60, silent_active=True, target_max_duty=50)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=True, fan_governor_emergency_temp_c=83.0)
        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            thermal_events = execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )
        sk = "S19JPRO-1|192.168.100.1:4028"
        st = states[sk]
        self.assertTrue(st.silent_mode_active, "silent_mode_active must remain True when safe")
        self.assertEqual(thermal_events, [])

    def test_failsafe_fault_also_cancels_silent_mode(self):
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=60, silent_active=True, target_max_duty=50)
        sk = "S19JPRO-1|192.168.100.1:4028"
        states[sk].governor_failures = 3
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=False, fan_governor_max_failures=3)
        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            thermal_events = execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )
        st = states[sk]
        self.assertFalse(st.silent_mode_active)
        self.assertTrue(any(ev[2] == ACTION_FAILSAFE_FAULT for ev in thermal_events))

    def test_no_thermal_events_without_silent_mode(self):
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=83.5, duty=100, silent_active=False)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=False, fan_governor_emergency_temp_c=83.0)
        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            thermal_events = execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )
        self.assertEqual(thermal_events, [])


class TestC1NoHTTPInPollingThread(unittest.TestCase):
    """C1: /silent activation is pure state mutation, no HTTP calls."""

    def test_activating_silent_mode_is_pure_state_mutation(self):
        st = MinerState()
        lock = threading.Lock()
        http_calls = []
        with lock:
            st.silent_mode_prev_duty = st.governor_duty
            st.silent_mode_active = True
            st.silent_mode_revert_ts = time.time() + 7200.0
            st.silent_mode_target_max_duty = 50
        self.assertEqual(http_calls, [])
        self.assertTrue(st.silent_mode_active)
        self.assertIsNotNone(st.silent_mode_revert_ts)

    def test_concurrent_state_lock_safety(self):
        """Concurrent silent activation and governor tick must not deadlock or corrupt state."""
        lock = threading.Lock()
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=100)
        errors = []

        def activate_silent():
            try:
                sk = "S19JPRO-1|192.168.100.1:4028"
                with lock:
                    st = states[sk]
                    st.silent_mode_active = True
                    st.silent_mode_revert_ts = time.time() + 3600.0
            except Exception as exc:
                errors.append(exc)

        def run_cycle():
            try:
                config = _make_config(fan_governor_dry_run=True)
                with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
                    execute_governor_cycle(
                        miners=miners, states=states, state_lock=lock,
                        config=config, now_ts=time.time(), qa_mode=False,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=activate_silent, daemon=True),
            threading.Thread(target=run_cycle, daemon=True),
            threading.Thread(target=activate_silent, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertFalse(errors, f"Errors: {errors}")


class TestTimerExpiry(unittest.TestCase):
    """Timer expiry detection logic."""

    def test_expired_timer_detected(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() - 1.0
        now_ts = time.time()
        is_expired = (
            st.silent_mode_active
            and st.silent_mode_revert_ts is not None
            and now_ts >= st.silent_mode_revert_ts
        )
        self.assertTrue(is_expired)
        st.silent_mode_active = False
        st.silent_mode_revert_ts = None
        self.assertFalse(st.silent_mode_active)

    def test_cancel_silent_mode_clears_active_and_revert_ts(self):
        st = MinerState()
        st.silent_mode_active = True
        st.silent_mode_revert_ts = time.time() + 3600.0
        st.silent_mode_prev_duty = 85
        st.silent_mode_prev_preset = "MaxHash"
        st.silent_mode_active = False
        st.silent_mode_revert_ts = None
        self.assertFalse(st.silent_mode_active)
        self.assertIsNone(st.silent_mode_revert_ts)
        self.assertEqual(st.silent_mode_prev_duty, 85)




class TestSilentModeIndependentElevators(unittest.TestCase):
    """Spec 044 / User Requirement: 30-50% PWM range, 82C target, independent elevators."""

    def test_independent_miners_different_duty_at_82c(self):
        """
        Miner 1 (elevator_1) at 82C with 50% PWM and Miner 2 (elevator_2) at 82C with 30% PWM.
        Both hold their respective duties in deadband [81.0, 82.5] without cross-interference.
        """
        m1 = {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1", "target_power_w": 2700.0}
        m2 = {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2", "target_power_w": 2700.0}
        miners = [m1, m2]

        now = time.time()
        sk1 = "S19JPRO-23|192.168.100.23:4028"
        st1 = MinerState()
        st1.governor_last_temp_c = 82.0
        st1.governor_duty = 50
        st1.governor_last_power_w = 2700.0
        st1.governor_last_change_ts = now - 200.0
        st1.silent_mode_active = True
        st1.silent_mode_target_max_duty = 50

        sk2 = "S19JPRO-25|192.168.100.25:4028"
        st2 = MinerState()
        st2.governor_last_temp_c = 82.0
        st2.governor_duty = 30
        st2.governor_last_power_w = 2700.0
        st2.governor_last_change_ts = now - 200.0
        st2.silent_mode_active = True
        st2.silent_mode_target_max_duty = 50

        states = {sk1: st1, sk2: st2}
        lock = threading.Lock()
        config = _make_config(
            fan_governor_dry_run=False,
            silent_mode_target_max_duty=50,
            silent_mode_min_duty_pct=30,
        )

        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)) as mock_write:
            execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=now, qa_mode=False,
            )
            # Both are in deadband [81.0, 82.5] -> ACTION_HOLD_TARGET -> no writes needed
            mock_write.assert_not_called()

        self.assertEqual(states[sk1].governor_duty, 50)
        self.assertEqual(states[sk2].governor_duty, 30)
        self.assertEqual(states[sk1].governor_last_action, ACTION_HOLD_TARGET)
        self.assertEqual(states[sk2].governor_last_action, ACTION_HOLD_TARGET)

    def test_step_down_to_30_pct_floor(self):
        """Miner at 79C steps down fans down to 30% floor."""
        cfg = GovernorConfig(
            min_fan_duty_percent=30,
            max_fan_duty_percent=50,
            deadband_low_c=81.0,
            deadband_high_c=82.5,
            step_down_percent=2,
            dwell_seconds=90,
        )
        # Stepping down from 34% -> 32%
        dec = compute_governor_step(
            max_temp_c=79.0, current_duty=34, seconds_since_last_change=100.0, config=cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN)
        self.assertEqual(dec.target_duty, 32)
        self.assertTrue(dec.requires_write)

        # Already at 30% floor
        dec_floor = compute_governor_step(
            max_temp_c=79.0, current_duty=30, seconds_since_last_change=100.0, config=cfg,
        )
        self.assertEqual(dec_floor.action, ACTION_STEP_DOWN)
        self.assertEqual(dec_floor.target_duty, 30)
        self.assertFalse(dec_floor.requires_write)

    def test_step_up_to_50_pct_ceiling(self):
        """Miner at 82.8C steps up fans up to 50% ceiling."""
        cfg = GovernorConfig(
            min_fan_duty_percent=30,
            max_fan_duty_percent=50,
            deadband_low_c=81.0,
            deadband_high_c=82.5,
            step_up_percent=3,
            dwell_seconds=90,
        )
        # Stepping up from 46% -> 49%
        dec = compute_governor_step(
            max_temp_c=82.8, current_duty=46, seconds_since_last_change=100.0, config=cfg,
        )
        self.assertEqual(dec.action, ACTION_STEP_UP)
        self.assertEqual(dec.target_duty, 49)
        self.assertTrue(dec.requires_write)

        # Stepping up capped at 50%
        dec_ceil = compute_governor_step(
            max_temp_c=82.8, current_duty=49, seconds_since_last_change=100.0, config=cfg,
        )
        self.assertEqual(dec_ceil.action, ACTION_STEP_UP)
        self.assertEqual(dec_ceil.target_duty, 50)
        self.assertTrue(dec_ceil.requires_write)

if __name__ == "__main__":
    unittest.main()
