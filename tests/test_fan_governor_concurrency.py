"""tests/test_fan_governor_concurrency.py
T018: Concurrency and timeout stress tests for Fan Governor (Spec 039).

Tests:
  1. Fleet timeout: a slow miner (10s) does not block the executor beyond 5s.
  2. /gov off fallback: sets governor_failures and returns safe result.
  3. Exception isolation: one miner throwing does not affect others.
  4. state_lock thread-safety: concurrent state updates under lock.
  5. Dry-run path: no hardware calls when dry_run=True.
  6. Failsafe trigger: governor triggers 100% after 3 consecutive failures.
"""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.fan_governor import (
        GovernorConfig,
        GovernorDecision,
        compute_governor_step,
        ACTION_EMERGENCY_SPIKE,
        ACTION_FAILSAFE_FAULT,
        ACTION_HOLD_DWELL,
        ACTION_HOLD_TARGET,
        ACTION_RECOVERY_MAX_COOLING,
        ACTION_STEP_DOWN,
        ACTION_STEP_UP,
    )
    from app.miner_monitor import MinerState, execute_governor_cycle
except ImportError:
    from fan_governor import (
        GovernorConfig,
        GovernorDecision,
        compute_governor_step,
        ACTION_EMERGENCY_SPIKE,
        ACTION_FAILSAFE_FAULT,
        ACTION_HOLD_DWELL,
        ACTION_HOLD_TARGET,
        ACTION_RECOVERY_MAX_COOLING,
        ACTION_STEP_DOWN,
        ACTION_STEP_UP,
    )
    from miner_monitor import MinerState, execute_governor_cycle  # type: ignore


def _make_config(**overrides) -> dict:
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
        "vnish_api_password": "admin",
    }
    cfg.update(overrides)
    return cfg


def _make_miner(n: int) -> dict:
    return {"name": f"S19JPRO-{n}", "host": f"192.168.100.{n}", "port": 4028}


def _make_states(miners: list, temp_c: float = 79.0, duty: int = 100) -> dict:
    states = {}
    for m in miners:
        sk = f"{m['name']}|{m['host']}:{m['port']}"
        st = MinerState()
        st.governor_last_temp_c = temp_c
        st.governor_duty = duty
        st.governor_last_change_ts = time.time() - 200.0  # dwell expired
        states[sk] = st
    return states


# ---------------------------------------------------------------------------
# Test 1: Fleet timeout — slow miner does not block beyond 5s
# ---------------------------------------------------------------------------
class TestFleetTimeout(unittest.TestCase):
    def test_slow_miner_does_not_block_executor(self):
        """safe_set_fan_duty for one miner that takes 10s must not delay the
        cycle beyond fleet_timeout=5.0s."""
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=100)
        lock = threading.Lock()
        config = _make_config(
            fan_governor_dry_run=False,
            fan_governor_fleet_timeout=2.0,  # short for test speed
            fan_governor_request_timeout=2.5,
        )

        call_count = {"n": 0}

        def slow_safe_set(host, pw, duty, timeout=2.5):
            call_count["n"] += 1
            time.sleep(10.0)  # Simulate very slow miner
            return True, None

        start = time.monotonic()
        with patch("app.miner_monitor.safe_set_fan_duty", slow_safe_set):
            execute_governor_cycle(
                miners=miners,
                states=states,
                state_lock=lock,
                config=config,
                now_ts=time.time(),
                qa_mode=False,
            )
        elapsed = time.monotonic() - start

        # Must not have blocked for 10s — fleet timeout should fire at ~2s
        self.assertLess(elapsed, 7.0,
                        f"Governor cycle blocked too long: {elapsed:.2f}s (fleet_timeout=2.0s)")


# ---------------------------------------------------------------------------
# Test 2: Dry-run — no hardware calls when dry_run=True
# ---------------------------------------------------------------------------
class TestDryRun(unittest.TestCase):
    def test_dry_run_no_hardware_write(self):
        """With dry_run=True, safe_set_fan_duty must never be called."""
        miners = [_make_miner(1), _make_miner(2)]
        states = _make_states(miners, temp_c=79.0, duty=100)  # Below deadband: STEP_DOWN
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=True)

        calls = []

        def mock_ssfd(host, pw, duty, timeout=2.5):
            calls.append(host)
            return True, None

        with patch("app.miner_monitor.safe_set_fan_duty", mock_ssfd):
            execute_governor_cycle(
                miners=miners,
                states=states,
                state_lock=lock,
                config=config,
                now_ts=time.time(),
                qa_mode=False,
            )

        self.assertEqual(calls, [], "safe_set_fan_duty called in dry_run mode!")

        # State must be updated even in dry_run
        for m in miners:
            sk = f"{m['name']}|{m['host']}:{m['port']}"
            st = states[sk]
            # Dry-run STEP_DOWN: duty should have been moved down
            self.assertIsNotNone(st.governor_last_action)

    def test_dry_run_duty_updated_in_state(self):
        """In dry_run mode, governor_duty must be updated in state even without
        hardware write."""
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=100)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=True)

        with patch("app.miner_monitor.safe_set_fan_duty", return_value=(True, None)):
            execute_governor_cycle(
                miners=miners, states=states, state_lock=lock,
                config=config, now_ts=time.time(), qa_mode=False,
            )

        sk = f"S19JPRO-1|192.168.100.1:4028"
        st = states[sk]
        self.assertEqual(st.governor_last_action, ACTION_STEP_DOWN,
                         f"Expected STEP_DOWN with T=79°C, got {st.governor_last_action}")
        self.assertIsNotNone(st.governor_duty)


# ---------------------------------------------------------------------------
# Test 3: Exception isolation — exception in one miner does not affect others
# ---------------------------------------------------------------------------
class TestExceptionIsolation(unittest.TestCase):
    def test_one_failing_miner_does_not_block_others(self):
        """If safe_set_fan_duty raises for miner-1, miner-2 must still complete."""
        miners = [_make_miner(1), _make_miner(2)]
        states = _make_states(miners, temp_c=79.0, duty=100)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=False, fan_governor_fleet_timeout=5.0)

        call_log = []

        def failing_ssfd(host, pw, duty, timeout=2.5):
            call_log.append(host)
            if "100.1" in host:
                raise ConnectionError("simulated hardware failure")
            return True, None

        with patch("app.miner_monitor.safe_set_fan_duty", failing_ssfd):
            # Must not raise
            try:
                execute_governor_cycle(
                    miners=miners, states=states, state_lock=lock,
                    config=config, now_ts=time.time(), qa_mode=False,
                )
            except Exception as exc:
                self.fail(f"execute_governor_cycle raised: {exc}")

        # miner-2 should still have been attempted
        self.assertIn("192.168.100.2", call_log,
                      "Miner-2 was not attempted after miner-1 failure")

        # Miner-1 should show a failure
        sk1 = "S19JPRO-1|192.168.100.1:4028"
        self.assertGreater(states[sk1].governor_failures, 0,
                           "Miner-1 should have incremented governor_failures")


# ---------------------------------------------------------------------------
# Test 4: state_lock thread-safety under concurrent access
# ---------------------------------------------------------------------------
class TestStateLockConcurrency(unittest.TestCase):
    def test_concurrent_state_mutations_no_corruption(self):
        """Concurrent execute_governor_cycle calls must not corrupt state."""
        miners = [_make_miner(1)]
        states = _make_states(miners, temp_c=79.0, duty=100)
        lock = threading.Lock()
        config = _make_config(fan_governor_dry_run=True)
        errors = []

        def run_cycle():
            try:
                execute_governor_cycle(
                    miners=miners, states=states, state_lock=lock,
                    config=config, now_ts=time.time(), qa_mode=False,
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run_cycle, daemon=True) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=10)

        self.assertFalse(errors, f"Exceptions under concurrent access: {errors}")

        sk = "S19JPRO-1|192.168.100.1:4028"
        st = states[sk]
        self.assertIsNotNone(st.governor_last_action)
        self.assertIsInstance(st.governor_duty, int)


# ---------------------------------------------------------------------------
# Test 5: Failsafe — 3 consecutive failures trigger FAILSAFE_FAULT at 100%
# ---------------------------------------------------------------------------
class TestFailsafeFault(unittest.TestCase):
    def test_failsafe_fires_after_3_failures(self):
        """After 3 consecutive HTTP failures, compute_governor_step must return
        FAILSAFE_FAULT with target_duty=100."""
        cfg = GovernorConfig(max_consecutive_failures=3)
        decision = compute_governor_step(
            max_temp_c=79.0,
            current_duty=85,
            seconds_since_last_change=200.0,
            consecutive_failures=3,
            config=cfg,
        )
        self.assertEqual(decision.action, ACTION_FAILSAFE_FAULT)
        self.assertEqual(decision.target_duty, 100)
        self.assertTrue(decision.is_emergency)
        self.assertTrue(decision.requires_write)

    def test_failsafe_requires_write_only_if_below_100(self):
        """FAILSAFE_FAULT must not require write if already at 100%."""
        cfg = GovernorConfig(max_consecutive_failures=3)
        decision = compute_governor_step(
            max_temp_c=79.0,
            current_duty=100,
            seconds_since_last_change=200.0,
            consecutive_failures=3,
            config=cfg,
        )
        self.assertEqual(decision.action, ACTION_FAILSAFE_FAULT)
        self.assertFalse(decision.requires_write)


# ---------------------------------------------------------------------------
# Test 6: Emergency spike — T >= 83°C fires immediately, ignores dwell
# ---------------------------------------------------------------------------
class TestEmergencySpike(unittest.TestCase):
    def test_emergency_ignores_dwell(self):
        """T >= 83.0°C must fire EMERGENCY_SPIKE even within dwell window."""
        cfg = GovernorConfig(dwell_seconds=90)
        decision = compute_governor_step(
            max_temp_c=83.5,
            current_duty=90,
            seconds_since_last_change=5.0,  # Well within dwell
            consecutive_failures=0,
            config=cfg,
        )
        self.assertEqual(decision.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(decision.target_duty, 100)
        self.assertTrue(decision.is_emergency)
        self.assertTrue(decision.requires_write)

    def test_emergency_no_write_if_already_100(self):
        """EMERGENCY_SPIKE must not require write if duty already 100%."""
        cfg = GovernorConfig()
        decision = compute_governor_step(
            max_temp_c=83.5,
            current_duty=100,
            seconds_since_last_change=5.0,
            config=cfg,
        )
        self.assertEqual(decision.action, ACTION_EMERGENCY_SPIKE)
        self.assertFalse(decision.requires_write)


# ---------------------------------------------------------------------------
# Test 7: Adaptive dwell — consecutive holds trigger longer dwell
# ---------------------------------------------------------------------------
class TestAdaptiveDwell(unittest.TestCase):
    def test_adaptive_dwell_applied_after_threshold(self):
        """When consecutive_holds >= 3, dwell_effective must equal adaptive_dwell_seconds."""
        cfg = GovernorConfig(
            dwell_seconds=90,
            adaptive_dwell_seconds=120,
            consecutive_holds_threshold=3,
        )
        decision = compute_governor_step(
            max_temp_c=79.0,
            current_duty=90,
            seconds_since_last_change=100.0,  # > 90s but < 120s
            consecutive_holds=3,
            config=cfg,
        )
        # Should be HOLD_DWELL because 100s < 120s adaptive dwell
        self.assertEqual(decision.action, ACTION_HOLD_DWELL)
        self.assertEqual(decision.dwell_effective, 120)

    def test_standard_dwell_below_threshold(self):
        """With consecutive_holds < 3, standard dwell_seconds applies."""
        cfg = GovernorConfig(
            dwell_seconds=90,
            adaptive_dwell_seconds=120,
            consecutive_holds_threshold=3,
        )
        decision = compute_governor_step(
            max_temp_c=79.0,
            current_duty=90,
            seconds_since_last_change=100.0,  # > 90s
            consecutive_holds=2,
            config=cfg,
        )
        # Should be STEP_DOWN because 100s > 90s and holds < 3
        self.assertEqual(decision.action, ACTION_STEP_DOWN)
        self.assertEqual(decision.dwell_effective, 90)


# ---------------------------------------------------------------------------
# Test 8: PWM floor — never below min_fan_duty_percent
# ---------------------------------------------------------------------------
class TestPWMFloor(unittest.TestCase):
    def test_step_down_respects_floor(self):
        """STEP_DOWN at floor must return floor, not lower."""
        cfg = GovernorConfig(min_fan_duty_percent=75, step_down_percent=2)
        decision = compute_governor_step(
            max_temp_c=79.0,
            current_duty=75,  # Already at floor
            seconds_since_last_change=200.0,
            config=cfg,
        )
        self.assertEqual(decision.action, ACTION_STEP_DOWN)
        self.assertEqual(decision.target_duty, 75)
        self.assertFalse(decision.requires_write,
                         "Should not require write if already at floor")


# ---------------------------------------------------------------------------
# Test 9: Autoswitch recovery — under target power forces 100% cooling
# ---------------------------------------------------------------------------
class TestAutoswitchRecovery(unittest.TestCase):
    def test_execute_governor_cycle_recovers_to_100_when_below_target_power(self):
        """When miner power is below target_power_w, governor cycle must force 100% duty."""
        miners = [
            {"name": "M25", "host": "192.168.100.25", "port": 4028, "target_power_w": 2500.0},
        ]
        lock = threading.Lock()
        states = {
            "M25|192.168.100.25:4028": MinerState(
                governor_duty=85,
                governor_last_temp_c=76.0,  # cool, would normally step down!
                governor_last_power_w=2299.0,  # below 2500W target
                governor_last_change_ts=0.0,
            )
        }
        cfg = _make_config(fan_governor_dry_run=True)
        execute_governor_cycle(miners, states, lock, cfg, now_ts=1000.0)

        st = states["M25|192.168.100.25:4028"]
        self.assertEqual(st.governor_last_action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(st.governor_duty, 100)

    def test_individual_miner_reasoning_different_targets_and_temperatures(self):
        """Miners must evaluate independently: one recovering to 100% does not prevent another from stepping down."""
        miners = [
            {"name": "M24", "host": "192.168.100.24", "port": 4028, "target_power_w": 2700.0},
            {"name": "M26", "host": "192.168.100.26", "port": 4028, "target_power_w": 2500.0},
        ]
        lock = threading.Lock()
        states = {
            "M24|192.168.100.24:4028": MinerState(
                governor_duty=100,
                governor_last_temp_c=81.0,
                governor_last_power_w=2499.0,  # Below 2700W target -> RECOVERY_MAX_COOLING (keep 100%)
                governor_last_change_ts=0.0,
            ),
            "M26|192.168.100.26:4028": MinerState(
                governor_duty=100,
                governor_last_temp_c=76.0,
                governor_last_power_w=2499.0,  # At 2500W target & cool -> STEP_DOWN to 98%
                governor_last_change_ts=0.0,
            ),
        }
        cfg = _make_config(
            fan_governor_dry_run=True,
            fan_governor_target_temp_c=83.0,
            fan_governor_deadband_low_c=82.0,
            fan_governor_step_down_pct=2,
            fan_governor_dwell_seconds=90,
        )
        execute_governor_cycle(miners, states, lock, cfg, now_ts=1000.0)

        st24 = states["M24|192.168.100.24:4028"]
        st26 = states["M26|192.168.100.26:4028"]

        # M24 is under target power -> stays at 100%
        self.assertEqual(st24.governor_last_action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(st24.governor_duty, 100)

        # M26 is AT target power and cool (76°C < 82°C) -> steps down to 98%
        self.assertEqual(st26.governor_last_action, ACTION_STEP_DOWN)
        self.assertEqual(st26.governor_duty, 98)


if __name__ == "__main__":
    unittest.main()
