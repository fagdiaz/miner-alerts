import unittest

from app.restart_intelligence import classify_restart


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


if __name__ == "__main__":
    unittest.main()
