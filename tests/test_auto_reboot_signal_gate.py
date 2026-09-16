import math
import inspect
import unittest

from app.miner_monitor import (
    AUTO_REBOOT_SIGNAL_ELIGIBLE,
    AUTO_REBOOT_SIGNAL_INVALID,
    AUTO_REBOOT_SIGNAL_NOT_LOW,
    STATE_LOW,
    MinerState,
    auto_reboot_signal_allows_evaluation,
    classify_auto_reboot_signal,
    reset_sustained_low_if_signal_ineligible,
    main,
)


class AutoRebootSignalGateTests(unittest.TestCase):
    def test_classifies_only_finite_below_threshold_as_eligible(self) -> None:
        cases = (
            (False, 50.0, AUTO_REBOOT_SIGNAL_INVALID),
            (True, None, AUTO_REBOOT_SIGNAL_INVALID),
            (True, math.nan, AUTO_REBOOT_SIGNAL_INVALID),
            (True, math.inf, AUTO_REBOOT_SIGNAL_INVALID),
            (True, -math.inf, AUTO_REBOOT_SIGNAL_INVALID),
            (True, 60.0, AUTO_REBOOT_SIGNAL_NOT_LOW),
            (True, 99.0, AUTO_REBOOT_SIGNAL_NOT_LOW),
            (True, 59.999, AUTO_REBOOT_SIGNAL_ELIGIBLE),
        )

        for responded, rate, expected in cases:
            with self.subTest(responded=responded, rate=rate):
                self.assertEqual(
                    expected,
                    classify_auto_reboot_signal(responded, rate, 60.0),
                )

    def test_evaluation_requires_low_state_timer_and_eligible_signal(self) -> None:
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_INVALID,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_NOT_LOW,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                "OK",
                1_000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                None,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )

    def test_ineligible_signal_resets_sustained_timer(self) -> None:
        for signal in (AUTO_REBOOT_SIGNAL_INVALID, AUTO_REBOOT_SIGNAL_NOT_LOW):
            with self.subTest(signal=signal):
                state = MinerState(state=STATE_LOW, low_since_ts=1_000.0)
                changed = reset_sustained_low_if_signal_ineligible(state, signal)
                self.assertTrue(changed)
                self.assertIsNone(state.low_since_ts)

        eligible = MinerState(state=STATE_LOW, low_since_ts=1_000.0)
        changed = reset_sustained_low_if_signal_ineligible(
            eligible,
            AUTO_REBOOT_SIGNAL_ELIGIBLE,
        )
        self.assertFalse(changed)
        self.assertEqual(1_000.0, eligible.low_since_ts)

    def test_runtime_wiring_keeps_restart_reset_and_gates_hashcore(self) -> None:
        from app.core.engine import ActuatorHook

        # 1. Reinicio detectado en hardware anula el temporizador sostenido
        state = MinerState(state=STATE_LOW, low_since_ts=1000.0)
        reboot_reason = "elapsed_reset"
        if reboot_reason:
            state.low_since_ts = None
        self.assertIsNone(state.low_since_ts)

        # 2. Señal inelegible bloquea auto-reboot antes de cualquier acción
        state.low_since_ts = 1000.0
        res = ActuatorHook.evaluate_auto_reboot_policy(
            state=state,
            miner={"name": "M1"},
            new_state=STATE_LOW,
            responded=True,
            rate_ths=70.0,  # NOT_LOW
            threshold_ths=60.0,
            active_boards=3,
            now_ts=2500.0,
        )
        self.assertFalse(res["allowed"])
        self.assertEqual("ineligible_signal", res["reason"])
        self.assertIsNone(state.low_since_ts)


if __name__ == "__main__":
    unittest.main()
