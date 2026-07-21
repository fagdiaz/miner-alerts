import json
import unittest
from pathlib import Path

from app.miner_monitor import (
    PersistentOutageNotificationCoordinator,
    StateChangeNotificationCoordinator,
    format_persistent_outage_reminder,
)


class StateChangeNotificationCoordinatorTests(unittest.TestCase):
    def test_groups_changes_across_adjacent_ticks(self) -> None:
        coordinator = StateChangeNotificationCoordinator(coalesce_seconds=30)
        coordinator.add(
            detected_ts=100.0,
            event_lines=["- 23: OK -> OFFLINE"],
            reboot_names=[],
        )
        coordinator.add(
            detected_ts=125.0,
            event_lines=["- 24: OK -> OFFLINE"],
            reboot_names=["24"],
        )

        self.assertIsNone(coordinator.pop_ready(now_ts=129.0))
        batch = coordinator.pop_ready(now_ts=130.0)

        self.assertIsNotNone(batch)
        self.assertEqual(
            ["- 23: OK -> OFFLINE", "- 24: OK -> OFFLINE"],
            batch["event_lines"],
        )
        self.assertEqual(["24"], batch["reboot_names"])
        self.assertFalse(coordinator.has_pending())

    def test_single_change_is_delivered_after_bound(self) -> None:
        coordinator = StateChangeNotificationCoordinator(coalesce_seconds=30)
        coordinator.add(
            detected_ts=100.0,
            event_lines=["- 23: OK -> LOW"],
            reboot_names=[],
        )

        self.assertIsNone(coordinator.pop_ready(now_ts=129.9))
        self.assertIsNotNone(coordinator.pop_ready(now_ts=130.0))

    def test_clear_discards_restart_recovery_noise(self) -> None:
        coordinator = StateChangeNotificationCoordinator(coalesce_seconds=30)
        coordinator.add(
            detected_ts=100.0,
            event_lines=["- 23: OFFLINE -> LOW"],
            reboot_names=[],
        )

        coordinator.clear()

        self.assertFalse(coordinator.has_pending())
        self.assertIsNone(coordinator.pop_ready(now_ts=1_000.0))


class PersistentOutageNotificationCoordinatorTests(unittest.TestCase):
    def test_production_defaults_are_bounded_and_enabled(self) -> None:
        config = json.loads(
            Path("app/config.example.json").read_text(encoding="utf-8")
        )

        self.assertEqual(30, config["state_change_coalesce_seconds"])
        self.assertTrue(config["notify_persistent_outage"])
        self.assertEqual(900, config["persistent_outage_initial_seconds"])
        self.assertEqual(1_800, config["persistent_outage_repeat_seconds"])

    def test_first_and_repeat_reminders_are_bounded(self) -> None:
        coordinator = PersistentOutageNotificationCoordinator(
            initial_seconds=900,
            repeat_seconds=1_800,
        )
        coordinator.observe(
            miner_key="24|192.168.100.24:4028",
            name_display="24",
            host="192.168.100.24",
            state="OFFLINE",
            rate_ths=None,
            threshold_ths=60.0,
            now_ts=100.0,
        )

        self.assertEqual([], coordinator.pop_due(now_ts=999.0))
        first = coordinator.pop_due(now_ts=1_000.0)
        self.assertEqual(["24"], [item["name_display"] for item in first])
        self.assertEqual([], coordinator.pop_due(now_ts=2_799.0))
        repeated = coordinator.pop_due(now_ts=2_800.0)
        self.assertEqual(["24"], [item["name_display"] for item in repeated])

    def test_due_outages_are_grouped_and_recovery_clears_one(self) -> None:
        coordinator = PersistentOutageNotificationCoordinator(
            initial_seconds=900,
            repeat_seconds=1_800,
        )
        for miner, state, rate in (
            ("23", "LOW", 42.0),
            ("24", "OFFLINE", None),
        ):
            coordinator.observe(
                miner_key=f"{miner}|host:{miner}",
                name_display=miner,
                host=f"192.168.100.{miner}",
                state=state,
                rate_ths=rate,
                threshold_ths=60.0,
                now_ts=100.0,
            )

        due = coordinator.pop_due(now_ts=1_000.0)
        self.assertEqual(["23", "24"], [item["name_display"] for item in due])
        message = format_persistent_outage_reminder(due, now_ts=1_000.0)
        self.assertIn("FALLA PERSISTENTE", message)
        self.assertIn("23: LOW | 42.00 TH/s < 60.00 TH/s", message)
        self.assertIn("24: OFFLINE | sin respuesta API 4028", message)

        coordinator.observe(
            miner_key="23|host:23",
            name_display="23",
            host="192.168.100.23",
            state="OK",
            rate_ths=99.0,
            threshold_ths=60.0,
            now_ts=1_100.0,
        )
        self.assertEqual(["24|host:24"], sorted(coordinator.active))

    def test_existing_bad_state_after_startup_still_gets_reminder(self) -> None:
        coordinator = PersistentOutageNotificationCoordinator(
            initial_seconds=900,
            repeat_seconds=1_800,
        )

        coordinator.observe(
            miner_key="24|host:24",
            name_display="24",
            host="192.168.100.24",
            state="OFFLINE",
            rate_ths=None,
            threshold_ths=60.0,
            now_ts=10_000.0,
        )

        self.assertEqual([], coordinator.pop_due(now_ts=10_899.0))
        self.assertEqual(1, len(coordinator.pop_due(now_ts=10_900.0)))

    def test_restart_recovery_defers_active_outage(self) -> None:
        coordinator = PersistentOutageNotificationCoordinator(
            initial_seconds=900,
            repeat_seconds=1_800,
        )
        coordinator.observe(
            miner_key="24|host:24",
            name_display="24",
            host="192.168.100.24",
            state="LOW",
            rate_ths=0.0,
            threshold_ths=60.0,
            now_ts=100.0,
        )

        coordinator.defer_active(now_ts=800.0)

        self.assertEqual([], coordinator.pop_due(now_ts=1_699.0))
        self.assertEqual(1, len(coordinator.pop_due(now_ts=1_700.0)))


if __name__ == "__main__":
    unittest.main()
