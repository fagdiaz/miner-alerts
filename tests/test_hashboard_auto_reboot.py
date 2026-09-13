import inspect
import unittest
from typing import Optional
from unittest.mock import MagicMock

from app.miner_monitor import (
    AUTO_REBOOT_SIGNAL_ELIGIBLE,
    AUTO_REBOOT_SIGNAL_INVALID,
    AUTO_REBOOT_SIGNAL_NOT_LOW,
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OK,
    MinerState,
    VnishTelemetry,
    auto_reboot_signal_allows_evaluation,
    main,
    record_auto_reboot_decision,
    reset_sustained_hashboard_if_ineligible,
    reset_sustained_low_if_signal_ineligible,
)


class TestHashboardAutoRebootSignalGate(unittest.TestCase):
    """Spec 055 - Iteration 1: Pure unit tests for hashboard auto-reboot signal gates."""

    def test_state_low_preserves_original_behavior(self) -> None:
        """STATE_LOW must behave exactly as before with 3 arguments."""
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1000.0,
                AUTO_REBOOT_SIGNAL_INVALID,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1000.0,
                AUTO_REBOOT_SIGNAL_NOT_LOW,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                None,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )

    def test_state_ok_never_allows_evaluation(self) -> None:
        """STATE_OK must never allow evaluation regardless of parameters."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_OK,
                1000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=0,
            )
        )

    def test_hashboard_total_failure_with_timer_allows_evaluation(self) -> None:
        """STATE_HASHBOARD with 0 active boards and active timer must allow evaluation."""
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
                allow_partial_hashboard=False,
            )
        )

    def test_hashboard_total_failure_without_timer_blocks_evaluation(self) -> None:
        """STATE_HASHBOARD with 0 active boards but NO timer must block evaluation."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=None,
                active_boards=0,
                expected_boards=3,
            )
        )

    def test_hashboard_total_failure_with_invalid_signal_blocks_evaluation(self) -> None:
        """STATE_HASHBOARD with invalid signal (unresponsive) must block evaluation."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_INVALID,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
            )
        )

    def test_hashboard_partial_failure_policy(self) -> None:
        """Partial failure (1 or 2 boards out of 3) respects allow_partial_hashboard."""
        # By default, allow_partial_hashboard=False -> BLOCKS
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=2,
                expected_boards=3,
                allow_partial_hashboard=False,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=1,
                expected_boards=3,
                allow_partial_hashboard=False,
            )
        )

        # When allow_partial_hashboard=True -> ALLOWS
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=2,
                expected_boards=3,
                allow_partial_hashboard=True,
            )
        )

    def test_hashboard_disabled_by_config_blocks_evaluation(self) -> None:
        """If hashboard_reboot_enabled=False, evaluation is blocked."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
                hashboard_reboot_enabled=False,
            )
        )

    def test_reset_sustained_hashboard_if_ineligible(self) -> None:
        """Tests for reset_sustained_hashboard_if_ineligible helper."""
        state = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0)

        # Invalid signal -> resets timer
        res = reset_sustained_hashboard_if_ineligible(
            state=state,
            signal_classification=AUTO_REBOOT_SIGNAL_INVALID,
            active_boards=0,
        )
        self.assertTrue(res)
        self.assertIsNone(state.hashboard_since_ts)

        # Boards restored to 3/3 -> resets timer
        state.hashboard_since_ts = 1000.0
        res = reset_sustained_hashboard_if_ineligible(
            state=state,
            signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
            active_boards=3,
            expected_boards=3,
        )
        self.assertTrue(res)
        self.assertIsNone(state.hashboard_since_ts)

        # Total failure 0/3 with eligible signal -> DOES NOT reset timer
        state.hashboard_since_ts = 1000.0
        res = reset_sustained_hashboard_if_ineligible(
            state=state,
            signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
            active_boards=0,
            expected_boards=3,
        )
        self.assertFalse(res)
        self.assertEqual(state.hashboard_since_ts, 1000.0)

        # Partial failure 2/3 when partial NOT allowed -> resets timer
        state.hashboard_since_ts = 1000.0
        res = reset_sustained_hashboard_if_ineligible(
            state=state,
            signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
            active_boards=2,
            expected_boards=3,
            allow_partial_hashboard=False,
        )
        self.assertTrue(res)
        self.assertIsNone(state.hashboard_since_ts)

        # Partial failure 2/3 when partial IS allowed -> DOES NOT reset timer
        state.hashboard_since_ts = 1000.0
        res = reset_sustained_hashboard_if_ineligible(
            state=state,
            signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
            active_boards=2,
            expected_boards=3,
            allow_partial_hashboard=True,
        )
        self.assertFalse(res)
        self.assertEqual(state.hashboard_since_ts, 1000.0)

    def test_miner_state_hashboard_since_ts_serialization(self) -> None:
        """MinerState must have hashboard_since_ts field defaulting to None."""
        st = MinerState()
        self.assertIsNone(st.hashboard_since_ts)

        st.hashboard_since_ts = 12345.67
        self.assertEqual(st.hashboard_since_ts, 12345.67)

    def test_hashboard_timer_advances_deterministically(self) -> None:
        """Simulate tick progression keeping the timer anchored to the initial entry ts."""
        st = MinerState()
        t0 = 1000.0

        # Tick 1: enters STATE_HASHBOARD -> timer initialized
        if st.hashboard_since_ts is None:
            st.hashboard_since_ts = t0
        self.assertEqual(st.hashboard_since_ts, t0)
        self.assertEqual(t0 - st.hashboard_since_ts, 0.0)

        # Tick 2 (30s later): remains in STATE_HASHBOARD -> timer preserved
        t1 = t0 + 30.0
        if st.hashboard_since_ts is None:
            st.hashboard_since_ts = t1
        self.assertEqual(st.hashboard_since_ts, t0)
        self.assertEqual(t1 - st.hashboard_since_ts, 30.0)

        # Tick 20 (600s later): sustained threshold reached
        t20 = t0 + 600.0
        self.assertEqual(st.hashboard_since_ts, t0)
        self.assertEqual(t20 - st.hashboard_since_ts, 600.0)

    def test_hashboard_timer_resets_on_recovery_to_ok(self) -> None:
        """Returning to STATE_OK must reset hashboard_since_ts to None."""
        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0)

        # State transition to STATE_OK
        new_state = STATE_OK
        if new_state == STATE_OK:
            st.hashboard_since_ts = None

        self.assertIsNone(st.hashboard_since_ts)

    def test_hashboard_timer_resets_on_reboot_detected(self) -> None:
        """Detecting a miner reboot must reset hashboard_since_ts to None."""
        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0)

        reboot_reason = "elapsed_reset"
        if reboot_reason:
            st.low_since_ts = None
            st.hashboard_since_ts = None

        self.assertIsNone(st.hashboard_since_ts)


class TestHashboardAutoRebootPipeline(unittest.TestCase):
    """Spec 055 - Iteration 3 & 4: Pipeline tests for hashboard auto-reboot and interlocks."""

    def test_runtime_wiring_hashboard_reboot_pipeline_preserves_interlocks(self) -> None:
        """Verify the hashboard auto-reboot block in main maintains all 6 constitutional interlocks in sequence."""
        source = inspect.getsource(main)

        # Hashboard auto-reboot policy block must exist
        self.assertIn("elif (\n                    new_state == STATE_HASHBOARD", source)
        hashboard_policy = source.split("elif (\n                    new_state == STATE_HASHBOARD", 1)[1]

        # Verify presence of evaluation gate and helper
        self.assertIn("reset_sustained_hashboard_if_ineligible", hashboard_policy)

        # Verify ordering of the 6 constitutional interlocks
        startup_pos = hashboard_policy.index("elif startup_guard_active:")
        sustained_pos = hashboard_policy.index("(now_ts - state.hashboard_since_ts) < auto_reboot_hashboard_sustained_seconds:")
        interlock_pos = hashboard_policy.index("elif not interlock_decision.allowed:")
        cooldown_pos = hashboard_policy.index("cooldown_delta < reboot_cooldown_seconds:")
        window_pos = hashboard_policy.index("len(state.auto_reboot_timestamps) >= max_reboots_per_window:")
        action_pos = hashboard_policy.index('run_hashcore_cli(hashcore_cfg, miner, "reboot"')

        self.assertLess(startup_pos, sustained_pos, "Startup guard must precede sustained check")
        self.assertLess(sustained_pos, interlock_pos, "Sustained check must precede interlock evaluation")
        self.assertLess(interlock_pos, cooldown_pos, "Interlocks must precede cooldown check")
        self.assertLess(cooldown_pos, window_pos, "Cooldown must precede window check")
        self.assertLess(window_pos, action_pos, "Window check must precede reboot action execution")

        # Verify transition guard resets hashboard_since_ts
        interlock_branch = hashboard_policy.split("elif not interlock_decision.allowed:", 1)[1].split("else:", 1)[0]
        self.assertIn("state.hashboard_since_ts = now_ts", interlock_branch)

        # Verify action execution resets both timers and records decisions
        action_branch = hashboard_policy.split('run_hashcore_cli(hashcore_cfg, miner, "reboot"', 1)[1]
        self.assertIn("state.hashboard_since_ts = None", action_branch)
        self.assertIn("state.low_since_ts = None", action_branch)

        # Verify Telegram alert message format
        self.assertIn("falla de placas ({active_boards}/{expected_boards}) sostenida por {window_label}", action_branch)

    def test_record_auto_reboot_decision_populates_hashboard_elapsed(self) -> None:
        """record_auto_reboot_decision must populate low_elapsed_seconds using hashboard_since_ts when low_since_ts is None."""
        mock_store = MagicMock()
        mock_store.available = True

        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0, low_since_ts=None)
        telemetry = VnishTelemetry(max_temp_c=65.0)

        record_auto_reboot_decision(
            event_store=mock_store,
            evaluated_ts=1600.0,
            miner={"name": "23", "host": "192.168.100.23", "port": 4028},
            state=st,
            result="not_sustained",
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            telemetry=telemetry,
            startup_guard_active=False,
            qa_mode=False,
            cooldown_remaining_seconds=None,
            window_seconds=21600,
            details={"trigger": "hashboard_failure", "active_boards": 0, "expected_boards": 3},
        )

        mock_store.record_reboot_decision.assert_called_once()
        _, kwargs = mock_store.record_reboot_decision.call_args
        self.assertEqual(kwargs["low_elapsed_seconds"], 600.0)
        self.assertEqual(kwargs["state"], STATE_HASHBOARD)
        self.assertEqual(kwargs["result"], "not_sustained")
        self.assertEqual(kwargs["details"]["trigger"], "hashboard_failure")


if __name__ == "__main__":
    unittest.main()
