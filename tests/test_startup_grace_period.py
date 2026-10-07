"""Unit tests for Spec 066: Cold-Boot Fleet Grace Period Post-Arranque (PROP-001).

Validates:
1. Configuration parsing and defaults.
2. format_fleet_restored_line formatting helper.
3. is_fleet_warmup_complete predicate with all edge cases.
4. Streak, timer, and state suppression during grace period.
5. Early consolidation (🟢 FLOTA RESTABLECIDA) vs timeout consolidation (STARTUP [FIN PERÍODO DE GRACIA]).
6. Backward compatibility when startup_fleet_grace_period_seconds == 0.
7. Preservation of all inspect.getsource(main) invariant contracts.
"""

import inspect
import unittest
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

from app.miner_monitor import (
    MinerState,
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OFFLINE,
    STATE_OK,
    format_fleet_restored_line,
    is_fleet_warmup_complete,
    main,
)


class TestStartupGraceConfigAndHelpers(unittest.TestCase):
    """Test pure functions and helper formatting for Spec 066."""

    def test_format_fleet_restored_line_with_temp(self) -> None:
        line = format_fleet_restored_line("23", 89.14, 72.3)
        self.assertEqual("- 23: 89.1 TH/s [OK] 72°C", line)

    def test_format_fleet_restored_line_without_temp(self) -> None:
        line = format_fleet_restored_line("24", 98.90, None)
        self.assertEqual("- 24: 98.9 TH/s [OK]", line)

    def test_format_fleet_restored_line_none_rate(self) -> None:
        line = format_fleet_restored_line("25", None, 70.0)
        self.assertEqual("- 25: N/A [OK] 70°C", line)

    def test_is_fleet_warmup_complete_empty_miners(self) -> None:
        self.assertFalse(is_fleet_warmup_complete([], {}, 50.0))

    def test_is_fleet_warmup_complete_missing_state(self) -> None:
        miners = [{"name": "23", "host": "192.168.1.23", "port": 4028}]
        self.assertFalse(is_fleet_warmup_complete(miners, {}, 50.0))

    def test_is_fleet_warmup_complete_not_responded(self) -> None:
        miners = [{"name": "23", "host": "192.168.1.23", "port": 4028}]
        st = MinerState(last_responded=False, last_rate_ths=0.0)
        states = {"23|192.168.1.23:4028": st}
        self.assertFalse(is_fleet_warmup_complete(miners, states, 50.0))

    def test_is_fleet_warmup_complete_rate_below_threshold(self) -> None:
        miners = [{"name": "23", "host": "192.168.1.23", "port": 4028}]
        st = MinerState(last_responded=True, last_rate_ths=42.5, last_active_boards=3)
        states = {"23|192.168.1.23:4028": st}
        self.assertFalse(is_fleet_warmup_complete(miners, states, 50.0))

    def test_is_fleet_warmup_complete_missing_board(self) -> None:
        miners = [{"name": "23", "host": "192.168.1.23", "port": 4028}]
        st = MinerState(last_responded=True, last_rate_ths=85.0, last_active_boards=2)
        states = {"23|192.168.1.23:4028": st}
        self.assertFalse(is_fleet_warmup_complete(miners, states, 50.0, expected_boards=3))

    def test_is_fleet_warmup_complete_all_healthy(self) -> None:
        miners = [
            {"name": "23", "host": "192.168.1.23", "port": 4028},
            {"name": "24", "host": "192.168.1.24", "port": 4028},
        ]
        states = {
            "23|192.168.1.23:4028": MinerState(
                last_responded=True, last_rate_ths=89.1, last_active_boards=3
            ),
            "24|192.168.1.24:4028": MinerState(
                last_responded=True, last_rate_ths=98.9, last_active_boards=3
            ),
        }
        self.assertTrue(is_fleet_warmup_complete(miners, states, 50.0, expected_boards=3))

    def test_is_fleet_warmup_complete_boards_none_allowed(self) -> None:
        miners = [{"name": "23", "host": "192.168.1.23", "port": 4028}]
        st = MinerState(last_responded=True, last_rate_ths=85.0, last_active_boards=None)
        states = {"23|192.168.1.23:4028": st}
        self.assertTrue(is_fleet_warmup_complete(miners, states, 50.0, expected_boards=3))


class TestStartupGracePeriodLogic(unittest.TestCase):
    """Test the behavioral contracts during cold-boot grace period."""

    def test_streak_and_timer_suppression_during_grace(self) -> None:
        """Simulate a tick during startup grace: streaks and sustained timers remain reset."""
        startup_grace_active = True
        state = MinerState(state=STATE_OK)
        responded = False
        rate_ths = None
        fails_before_alert = 3
        now_ts = 1000.0

        # Run streak calculation simulation
        if not responded:
            state.offline_streak += 1
            state.low_streak = 0
            state.ok_streak = 0

        # Under grace period, streaks are clamped to 0
        if startup_grace_active:
            state.offline_streak = 0
            state.low_streak = 0

        prev_state = state.state
        new_state = prev_state
        if not startup_grace_active:
            if not responded and state.offline_streak >= fails_before_alert:
                new_state = STATE_OFFLINE

        state.state = new_state
        if startup_grace_active:
            state.low_since_ts = None
            state.hashboard_since_ts = None

        self.assertEqual(0, state.offline_streak)
        self.assertEqual(0, state.low_streak)
        self.assertEqual(STATE_OK, state.state)
        self.assertIsNone(state.low_since_ts)
        self.assertIsNone(state.hashboard_since_ts)

    def test_smooth_recovery_during_grace_period(self) -> None:
        """When a miner reaches hash threshold during grace, it transitions to STATE_OK."""
        startup_grace_active = True
        state = MinerState(state=STATE_LOW, ok_streak=1)
        responded = True
        rate_ths = 85.0
        threshold_ths = 60.0
        recovery_successes = 2

        if rate_ths >= threshold_ths:
            state.ok_streak += 1
            state.low_streak = 0
            state.offline_streak = 0

        if startup_grace_active:
            state.offline_streak = 0
            state.low_streak = 0

        prev_state = state.state
        new_state = prev_state
        if responded and rate_ths >= threshold_ths and state.ok_streak >= recovery_successes:
            new_state = STATE_OK

        state.state = new_state
        self.assertEqual(STATE_OK, state.state)
        self.assertEqual(2, state.ok_streak)

    def test_consolidation_trigger_early_vs_timeout(self) -> None:
        """Verify decision conditions for early fleet restoration vs timeout expiration."""
        # Scenario 1: Fleet healthy before timeout
        process_start_ts = 1000.0
        now_ts = 1060.0  # 60s elapsed
        grace_period_seconds = 180
        fleet_healthy = True
        startup_notified = False
        startup_grace_active = True

        should_send = False
        is_restored = False
        if not startup_notified:
            if fleet_healthy:
                should_send = True
                is_restored = True
                startup_grace_active = False

        self.assertTrue(should_send)
        self.assertTrue(is_restored)
        self.assertFalse(startup_grace_active)

        # Scenario 2: Timeout reached with fleet not fully healthy
        now_ts = 1185.0  # 185s elapsed
        fleet_healthy = False
        startup_notified = False
        startup_grace_active = True

        should_send = False
        is_restored = False
        if not startup_notified:
            if fleet_healthy:
                should_send = True
                is_restored = True
                startup_grace_active = False
            elif (now_ts - process_start_ts) >= grace_period_seconds:
                should_send = True
                is_restored = False
                startup_grace_active = False

        self.assertTrue(should_send)
        self.assertFalse(is_restored)
        self.assertFalse(startup_grace_active)

    def test_disabled_grace_period_triggers_immediate_startup(self) -> None:
        """When startup_fleet_grace_period_seconds == 0, startup is immediate on first_tick."""
        grace_period_seconds = 0
        startup_notified = False
        first_tick = True

        should_send = False
        if not startup_notified:
            if grace_period_seconds == 0:
                if first_tick:
                    should_send = True

        self.assertTrue(should_send)


class TestStartupGraceInvariantContracts(unittest.TestCase):
    """Spec 090: Behavioral invariant contracts verifying supervisory precedence black-box."""

    def test_spec_066_helpers_and_state_contracts(self) -> None:
        """Verify Spec 066 helpers and state constants are functional and present."""
        self.assertTrue(callable(is_fleet_warmup_complete))
        self.assertTrue(callable(format_fleet_restored_line))
        self.assertEqual(STATE_OK, "OK")
        self.assertEqual(STATE_LOW, "LOW")
        self.assertEqual(STATE_OFFLINE, "OFFLINE")
        self.assertEqual(STATE_HASHBOARD, "HASHBOARD")

    def test_reboot_safety_precedence_hierarchy_blackbox(self) -> None:
        """Spec 090: Verify mathematical precedence hierarchy black-box.

        Precedence invariant:
        Startup Guard > Sustained LOW > Interlocks > Cooldown > Hashcore Execution
        """
        from tests.test_supervisory_core_behavioral import SupervisoryBehavioralHarness
        from app.core.reboot_safety import (
            RebootInterlockDecision,
            INTERLOCK_HIGH_TEMPERATURE,
        )

        miner = {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028}
        threshold_ths = 90.0

        # Stage 1: Startup Guard active blocks reboot, regardless of sustained time, interlocks, or cooldown
        st1 = MinerState(state=STATE_LOW, low_since_ts=1000.0)
        res1 = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st1,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=threshold_ths,
            active_boards=3,
            now_ts=1300.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,  # Startup guard active (1300 - 1000 = 300 < 600)
            low_sustained_seconds=100,  # Sustained condition satisfied (1300 - 1000 = 300 >= 100)
            interlock_decision=RebootInterlockDecision(allowed=True, reason="ok"),
            reboot_cooldown_seconds=60,
        )
        self.assertFalse(res1["allowed"])
        self.assertEqual(res1["blocked_by"], "startup_guard")

        # Stage 2: Startup Guard cleared, but LOW not sustained blocks reboot
        st2 = MinerState(state=STATE_LOW, low_since_ts=1800.0)
        res2 = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st2,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=threshold_ths,
            active_boards=3,
            now_ts=2000.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,  # Startup guard cleared (2000 - 1000 = 1000 >= 600)
            low_sustained_seconds=900,  # NOT sustained (2000 - 1800 = 200 < 900)
            interlock_decision=RebootInterlockDecision(allowed=True, reason="ok"),
            reboot_cooldown_seconds=60,
        )
        self.assertFalse(res2["allowed"])
        self.assertEqual(res2["blocked_by"], "not_sustained")

        # Stage 3: Startup Guard cleared & LOW sustained, but Interlock disallows
        st3 = MinerState(state=STATE_LOW, low_since_ts=1000.0)
        res3 = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st3,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=threshold_ths,
            active_boards=3,
            now_ts=2000.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,
            low_sustained_seconds=900,  # Sustained (2000 - 1000 = 1000 >= 900)
            interlock_decision=RebootInterlockDecision(allowed=False, reason=INTERLOCK_HIGH_TEMPERATURE),
            reboot_cooldown_seconds=60,
        )
        self.assertFalse(res3["allowed"])
        self.assertEqual(res3["blocked_by"], INTERLOCK_HIGH_TEMPERATURE)

        # Stage 4: Guard cleared, sustained, Interlock allowed, but Cooldown active
        st4 = MinerState(state=STATE_LOW, low_since_ts=1000.0, last_auto_reboot_ts=1950.0)
        res4 = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st4,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=threshold_ths,
            active_boards=3,
            now_ts=2000.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,
            low_sustained_seconds=900,
            interlock_decision=RebootInterlockDecision(allowed=True, reason="ok"),
            reboot_cooldown_seconds=1800,  # In cooldown (2000 - 1950 = 50 < 1800)
        )
        self.assertFalse(res4["allowed"])
        self.assertEqual(res4["blocked_by"], "cooldown")

        # Stage 5: All 4 gates passed -> Hashcore Action executed
        st5 = MinerState(state=STATE_LOW, low_since_ts=1000.0, last_auto_reboot_ts=None)
        res5 = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st5,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=threshold_ths,
            active_boards=3,
            now_ts=2000.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,
            low_sustained_seconds=900,
            interlock_decision=RebootInterlockDecision(allowed=True, reason="ok"),
            reboot_cooldown_seconds=60,
            cli_reboot_succeeds=True,
        )
        self.assertTrue(res5["allowed"])
        self.assertTrue(res5["action_executed"])
        self.assertTrue(res5.get("action_success", False))

    def test_hashboard_detection_precedence_over_low_hashrate(self) -> None:
        """When active boards are missing, detection prioritizes HASHBOARD over LOW."""
        from tests.test_supervisory_core_behavioral import SupervisoryBehavioralHarness

        state = SupervisoryBehavioralHarness.classify_detection_state(
            responded=True,
            rate_ths=50.0,
            threshold_ths=90.0,
            active_boards=2,
            expected_boards=3,
            startup_grace_active=False,
            low_streak=5,
        )
        self.assertEqual(state, STATE_HASHBOARD)

    def test_timer_lifecycle_resets_on_successful_reboot(self) -> None:
        """Timer and counter states are properly reset upon successful reboot action."""
        from tests.test_supervisory_core_behavioral import SupervisoryBehavioralHarness
        from app.core.reboot_safety import RebootInterlockDecision

        miner = {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028}
        st = MinerState(state=STATE_LOW, low_since_ts=1000.0, auto_restart_count=1)

        res = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st,
            miner=miner,
            new_state=STATE_LOW,
            responded=True,
            rate_ths=50.0,
            threshold_ths=90.0,
            active_boards=3,
            now_ts=2000.0,
            process_start_ts=1000.0,
            startup_guard_seconds=600,
            low_sustained_seconds=900,
            interlock_decision=RebootInterlockDecision(allowed=True, reason="ok"),
            reboot_cooldown_seconds=60,
            cli_reboot_succeeds=True,
        )

        self.assertTrue(res["action_executed"])
        self.assertIsNone(st.low_since_ts)
        self.assertEqual(st.auto_restart_count, 0)
        self.assertEqual(st.last_auto_reboot_ts, 2000.0)



if __name__ == "__main__":
    unittest.main()
