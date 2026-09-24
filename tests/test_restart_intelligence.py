import unittest

from app.core.restart_intelligence import classify_restart


class RestartIntelligenceTests(unittest.TestCase):
    def test_without_recent_action_is_unexpected(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_reset",
            detected_ts=10_000.0,
            last_manual_action_ts=None,
            last_auto_action_ts=None,
            attribution_window_seconds=900,
        )

        self.assertEqual("unexpected", result.classification)
        self.assertEqual("critical", result.severity)
        self.assertIsNone(result.action_source)

    def test_recent_manual_action_is_expected_manual(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=9_700.0,
            last_auto_action_ts=None,
            attribution_window_seconds=900,
        )

        self.assertEqual("expected_manual", result.classification)
        self.assertEqual("manual", result.action_source)
        self.assertEqual(300.0, result.action_age_seconds)

    def test_recent_auto_action_is_expected_auto(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=None,
            last_auto_action_ts=9_950.0,
            attribution_window_seconds=900,
        )

        self.assertEqual("expected_auto", result.classification)
        self.assertEqual("auto", result.action_source)

    def test_newest_qualifying_action_wins(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=9_950.0,
            last_auto_action_ts=9_900.0,
            attribution_window_seconds=900,
        )

        self.assertEqual("expected_manual", result.classification)
        self.assertEqual(9_950.0, result.action_ts)

    def test_expired_action_is_not_attributed(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=9_000.0,
            last_auto_action_ts=None,
            attribution_window_seconds=900,
        )

        self.assertEqual("unexpected", result.classification)

    def test_small_future_skew_is_clamped(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=10_005.0,
            last_auto_action_ts=None,
            attribution_window_seconds=900,
            skew_tolerance_seconds=10,
        )

        self.assertEqual("expected_manual", result.classification)
        self.assertEqual(0.0, result.action_age_seconds)

    def test_large_future_skew_is_rejected(self) -> None:
        result = classify_restart(
            restart_reason="elapsed_drop",
            detected_ts=10_000.0,
            last_manual_action_ts=10_020.0,
            last_auto_action_ts=None,
            attribution_window_seconds=900,
            skew_tolerance_seconds=10,
        )

        self.assertEqual("unexpected", result.classification)


    def test_recent_preset_change_is_expected_preset(self) -> None:
        """Un reinicio dentro de la ventana de gracia de un preset enviado por el monitor
        debe clasificarse como 'expected_preset', no 'unexpected'."""
        result = classify_restart(
            restart_reason="elapsed_reset",
            detected_ts=10_000.0,
            last_manual_action_ts=None,
            last_auto_action_ts=None,
            last_preset_change_ts=9_800.0,  # 200s antes del reinicio, dentro de 900s
            attribution_window_seconds=900,
        )

        self.assertEqual("expected_preset", result.classification)
        self.assertEqual("info", result.severity)
        self.assertEqual("preset", result.action_source)
        self.assertEqual(200.0, result.action_age_seconds)

    def test_expired_preset_change_falls_back_to_unexpected(self) -> None:
        """Un preset enviado hace más tiempo que la ventana de atribución no debe
        proteger contra la clasificación 'unexpected'."""
        result = classify_restart(
            restart_reason="elapsed_reset",
            detected_ts=10_000.0,
            last_manual_action_ts=None,
            last_auto_action_ts=None,
            last_preset_change_ts=9_000.0,  # hace 1000s, fuera de la ventana de 900s
            attribution_window_seconds=900,
        )

        self.assertEqual("unexpected", result.classification)
        self.assertEqual("critical", result.severity)

    def test_preset_ts_wins_over_older_auto_action(self) -> None:
        """Cuando tanto auto como preset son candidatos, el más reciente (preset) debe ganar."""
        result = classify_restart(
            restart_reason="elapsed_reset",
            detected_ts=10_000.0,
            last_manual_action_ts=None,
            last_auto_action_ts=9_500.0,   # 500s antes
            last_preset_change_ts=9_800.0,  # 200s antes — más reciente
            attribution_window_seconds=900,
        )

        self.assertEqual("expected_preset", result.classification)
        self.assertEqual("preset", result.action_source)
        self.assertEqual(9_800.0, result.action_ts)


if __name__ == "__main__":
    unittest.main()
