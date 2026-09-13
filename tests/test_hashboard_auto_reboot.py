import unittest
from typing import Optional

from app.miner_monitor import (
    AUTO_REBOOT_SIGNAL_ELIGIBLE,
    AUTO_REBOOT_SIGNAL_INVALID,
    AUTO_REBOOT_SIGNAL_NOT_LOW,
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OK,
    MinerState,
    auto_reboot_signal_allows_evaluation,
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


if __name__ == "__main__":
    unittest.main()
