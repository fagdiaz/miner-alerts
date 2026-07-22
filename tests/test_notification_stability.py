import json
import unittest
from pathlib import Path

from app.alert_episodes import IrregularEpisodeCoordinator


class EpisodeNotificationConfigurationTests(unittest.TestCase):
    def test_production_defaults_are_bounded_and_enabled(self) -> None:
        config = json.loads(
            Path("app/config.example.json").read_text(encoding="utf-8")
        )

        self.assertEqual(30, config["state_change_coalesce_seconds"])
        self.assertTrue(config["notify_persistent_outage"])
        self.assertEqual(
            [300, 600, 900, 1800, 3600, 7200],
            config["persistent_outage_schedule_seconds"],
        )
        self.assertEqual(3_600, config["persistent_outage_repeat_seconds"])

    def test_startup_acknowledgement_prevents_duplicate_initial_alert(self) -> None:
        coordinator = IrregularEpisodeCoordinator(
            coalesce_seconds=30,
            reminder_schedule_seconds=(300, 600, 900, 1800, 3600, 7200),
            steady_repeat_seconds=3600,
        )
        coordinator.observe(
            miner_key="24|host:24",
            name_display="24",
            host="192.168.100.24",
            previous_state="OK",
            state="LOW",
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            now_ts=100.0,
        )

        coordinator.acknowledge_active_initials()

        self.assertTrue(coordinator.pop_due(now_ts=130.0).empty)
        self.assertEqual(1, len(coordinator.pop_due(now_ts=400.0).persistent))


if __name__ == "__main__":
    unittest.main()
