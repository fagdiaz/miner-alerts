import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.liveness import (
    MaintenanceLease,
    MonitorHeartbeat,
    WatchdogIncidentState,
    assess_liveness,
    decide_notification,
    load_heartbeat,
    load_incident_state,
    load_maintenance_lease,
    render_liveness_assessment,
    write_incident_state,
    write_maintenance_lease,
    write_heartbeat_atomic,
)
from tools import monitor_watchdog


def heartbeat(**overrides) -> MonitorHeartbeat:
    values = {
        "pid": 1234,
        "process_start_ts": 900.0,
        "tick_sequence": 7,
        "last_tick_completed_ts": 1000.0,
        "telegram_poller_ts": 995.0,
        "telegram_sender_ts": 998.0,
        "queue_depth": 0,
        "collector_age_seconds": 120.0,
    }
    values.update(overrides)
    return MonitorHeartbeat(**values)


class HeartbeatContractTests(unittest.TestCase):
    def test_atomic_round_trip_has_versioned_sanitized_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "monitor_heartbeat.json"
            write_heartbeat_atomic(path, heartbeat())

            loaded, error = load_heartbeat(path)

            self.assertIsNone(error)
            self.assertEqual(7, loaded.tick_sequence)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual(
                {
                    "schema_version",
                    "pid",
                    "process_start_ts",
                    "tick_sequence",
                    "last_tick_completed_ts",
                    "telegram_poller_ts",
                    "telegram_sender_ts",
                    "queue_depth",
                    "collector_age_seconds",
                },
                set(payload),
            )
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_missing_malformed_and_unsupported_schema_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heartbeat.json"
            self.assertEqual((None, "heartbeat_missing"), load_heartbeat(path))
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual((None, "heartbeat_malformed"), load_heartbeat(path))
            path.write_text('{"schema_version":99}', encoding="utf-8")
            self.assertEqual((None, "heartbeat_schema_unsupported"), load_heartbeat(path))

    def test_windows_utf8_bom_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "heartbeat.json"
            payload = json.dumps(heartbeat().to_dict())
            path.write_text(payload, encoding="utf-8-sig")

            loaded, error = load_heartbeat(path)

            self.assertIsNone(error)
            self.assertEqual(7, loaded.tick_sequence)

    def test_incident_and_maintenance_state_round_trip_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incident_path = root / "watchdog_state.json"
            maintenance_path = root / "maintenance.json"
            state = WatchdogIncidentState(
                is_open=True,
                reason_codes=("tick_stale",),
                opened_ts=1000.0,
                last_seen_ts=1010.0,
                last_notified_ts=1000.0,
                notification_count=1,
            )
            lease = MaintenanceLease(expires_ts=1060.0, reason="upgrade")

            write_incident_state(incident_path, state)
            write_maintenance_lease(maintenance_path, lease)

            self.assertEqual(state, load_incident_state(incident_path))
            self.assertEqual(lease, load_maintenance_lease(maintenance_path))
            self.assertEqual([], list(root.glob("*.tmp")))


class LivenessAssessmentTests(unittest.TestCase):
    def test_fresh_heartbeat_is_healthy(self) -> None:
        result = assess_liveness(
            now_ts=1010.0,
            heartbeat=heartbeat(),
            service_state="running",
            process_alive=True,
            tick_stale_seconds=120,
            worker_stale_seconds=120,
            collector_stale_seconds=3600,
        )
        self.assertTrue(result.healthy)
        self.assertEqual((), result.reason_codes)

    def test_service_process_tick_and_workers_are_classified_separately(self) -> None:
        result = assess_liveness(
            now_ts=1300.0,
            heartbeat=heartbeat(
                telegram_poller_ts=900.0,
                telegram_sender_ts=910.0,
                collector_age_seconds=4000.0,
            ),
            service_state="stopped",
            process_alive=False,
            tick_stale_seconds=120,
            worker_stale_seconds=120,
            collector_stale_seconds=3600,
        )
        self.assertFalse(result.healthy)
        self.assertEqual(
            {
                "service_stopped",
                "process_missing",
                "tick_stale",
                "telegram_poller_stale",
                "telegram_sender_stale",
                "collector_stale",
            },
            set(result.reason_codes),
        )

    def test_future_timestamp_is_clock_skew_not_fresh(self) -> None:
        result = assess_liveness(
            now_ts=1000.0,
            heartbeat=heartbeat(last_tick_completed_ts=1020.0),
            service_state="running",
            process_alive=True,
            tick_stale_seconds=120,
            worker_stale_seconds=120,
            collector_stale_seconds=3600,
            clock_skew_tolerance_seconds=5,
        )
        self.assertFalse(result.healthy)
        self.assertIn("clock_skew", result.reason_codes)

    def test_active_maintenance_suppresses_notification_but_not_failure(self) -> None:
        result = assess_liveness(
            now_ts=1000.0,
            heartbeat=None,
            heartbeat_error="heartbeat_missing",
            service_state="stopped",
            process_alive=False,
            maintenance=MaintenanceLease(expires_ts=1060.0, reason="upgrade"),
        )
        self.assertFalse(result.healthy)
        self.assertTrue(result.suppressed)
        self.assertIn("heartbeat_missing", result.reason_codes)


class WatchdogNotificationTests(unittest.TestCase):
    def test_open_dedupe_reminder_and_recovery_are_deterministic(self) -> None:
        state = WatchdogIncidentState()
        bad = assess_liveness(
            now_ts=1000.0,
            heartbeat=None,
            heartbeat_error="heartbeat_missing",
            service_state="running",
            process_alive=False,
        )
        action, state = decide_notification(
            bad, state, now_ts=1000.0, reminder_schedule_seconds=(300, 900, 3600)
        )
        self.assertEqual("open", action)
        action, state = decide_notification(
            bad, state, now_ts=1200.0, reminder_schedule_seconds=(300, 900, 3600)
        )
        self.assertEqual("none", action)
        action, state = decide_notification(
            bad, state, now_ts=1300.0, reminder_schedule_seconds=(300, 900, 3600)
        )
        self.assertEqual("reminder", action)

        good = assess_liveness(
            now_ts=1310.0,
            heartbeat=heartbeat(
                last_tick_completed_ts=1310.0,
                telegram_poller_ts=1310.0,
                telegram_sender_ts=1310.0,
            ),
            service_state="running",
            process_alive=True,
        )
        action, state = decide_notification(
            good, state, now_ts=1310.0, reminder_schedule_seconds=(300, 900, 3600)
        )
        self.assertEqual("recovery", action)
        self.assertFalse(state.is_open)

    def test_maintenance_does_not_open_incident_and_expires_by_timestamp(self) -> None:
        state = WatchdogIncidentState()
        suppressed = assess_liveness(
            now_ts=1000.0,
            heartbeat=None,
            heartbeat_error="heartbeat_missing",
            service_state="stopped",
            process_alive=False,
            maintenance=MaintenanceLease(expires_ts=1010.0, reason="maintenance"),
        )
        action, state = decide_notification(suppressed, state, now_ts=1000.0)
        self.assertEqual("none", action)
        self.assertFalse(state.is_open)

        expired = assess_liveness(
            now_ts=1020.0,
            heartbeat=None,
            heartbeat_error="heartbeat_missing",
            service_state="stopped",
            process_alive=False,
            maintenance=MaintenanceLease(expires_ts=1010.0, reason="maintenance"),
        )
        action, state = decide_notification(expired, state, now_ts=1020.0)
        self.assertEqual("open", action)

    def test_render_contains_component_evidence_without_secrets(self) -> None:
        result = assess_liveness(
            now_ts=1300.0,
            heartbeat=heartbeat(telegram_poller_ts=900.0),
            service_state="running",
            process_alive=True,
            worker_stale_seconds=120,
        )

        rendered = render_liveness_assessment(result, event="open")

        self.assertIn("telegram_poller_stale", rendered)
        self.assertIn("Telegram poller: 400s", rendered)
        self.assertNotIn("bot_token", rendered)
        self.assertNotIn("chat_id", rendered)


class WatchdogRuntimeTests(unittest.TestCase):
    def _watchdog_config(self, root: Path) -> Path:
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "telegram": {"bot_token": "test-token", "chat_id": "123"},
                    "liveness": {
                        "heartbeat_path": str(root / "heartbeat.json"),
                        "watchdog_state_path": str(root / "state.json"),
                        "maintenance_path": str(root / "maintenance.json"),
                        "watchdog_log_path": str(root / "watchdog.log"),
                    },
                }
            ),
            encoding="utf-8",
        )
        return config_path

    def test_query_service_parses_english_and_spanish_output(self) -> None:
        for label in ("STATE", "ESTADO"):
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{label} : 4 RUNNING\nPID : 32796\n",
                stderr="",
            )
            with mock.patch.object(
                monitor_watchdog.subprocess, "run", return_value=completed
            ):
                self.assertEqual(
                    ("running", 32796), monitor_watchdog.query_service("MinerAlerts")
                )

    def test_process_exists_reports_current_process(self) -> None:
        self.assertTrue(monitor_watchdog.process_exists(os.getpid()))

    def test_notification_redacts_token_on_http_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "watchdog.log"
            token = "secret-token-value"
            config = {
                "telegram": {"bot_token": token, "chat_id": "123"},
            }
            with mock.patch.object(
                monitor_watchdog.requests,
                "post",
                side_effect=RuntimeError(f"request failed for {token}"),
            ):
                sent = monitor_watchdog.send_notification(
                    config, "test", log_path=log_path, event="open"
                )

            self.assertFalse(sent)
            logged = log_path.read_text(encoding="utf-8")
            self.assertNotIn(token, logged)
            self.assertIn("<redacted>", logged)
            self.assertIn("send_error", logged)

    def test_no_notify_does_not_consume_incident_delivery_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._watchdog_config(root)
            argv = [
                "monitor_watchdog.py",
                "--config",
                str(config_path),
                "--no-notify",
            ]
            with (
                mock.patch.object(monitor_watchdog.sys, "argv", argv),
                mock.patch.object(
                    monitor_watchdog, "query_service", return_value=("running", 123)
                ),
            ):
                self.assertEqual(0, monitor_watchdog.main())

            self.assertFalse((root / "state.json").exists())

    def test_failed_delivery_retries_same_incident_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._watchdog_config(root)
            argv = ["monitor_watchdog.py", "--config", str(config_path)]
            with (
                mock.patch.object(monitor_watchdog.sys, "argv", argv),
                mock.patch.object(
                    monitor_watchdog, "query_service", return_value=("running", 123)
                ),
                mock.patch.object(
                    monitor_watchdog, "send_notification", return_value=False
                ) as sender,
            ):
                self.assertEqual(0, monitor_watchdog.main())
                self.assertEqual(0, monitor_watchdog.main())

            self.assertEqual(2, sender.call_count)
            persisted = load_incident_state(root / "state.json")
            self.assertFalse(persisted.is_open)
            self.assertEqual(0, persisted.notification_count)


class WatchdogIsolationTests(unittest.TestCase):
    def test_production_example_has_bounded_liveness_defaults(self) -> None:
        config = json.loads(Path("app/config.example.json").read_text(encoding="utf-8"))
        liveness = config["liveness"]
        self.assertTrue(liveness["enabled"])
        self.assertEqual(120, liveness["tick_stale_seconds"])
        self.assertEqual(120, liveness["worker_stale_seconds"])
        self.assertEqual([300, 900, 3600], liveness["reminder_schedule_seconds"])
        self.assertLessEqual(liveness["maintenance_max_seconds"], 3600)

    def test_monitor_publishes_heartbeat_after_state_persistence(self) -> None:
        source = Path("app/miner_monitor.py").read_text(encoding="utf-8")
        tick_tail = source[source.index("while True:\n            tick_start") :]
        self.assertIn("write_heartbeat_atomic(", tick_tail)
        self.assertLess(
            tick_tail.rindex("save_state(state_path, states, current_last_update_id)"),
            tick_tail.index("write_heartbeat_atomic("),
        )
        self.assertLess(
            tick_tail.index("write_heartbeat_atomic("),
            tick_tail.index("time.sleep(poll_seconds)"),
        )
        heartbeat_block = tick_tail[
            tick_tail.index("if heartbeat_enabled:") : tick_tail.index(
                "first_tick = False"
            )
        ]
        self.assertLess(
            heartbeat_block.index("try:"),
            heartbeat_block.index("event_store.latest_collector_run()"),
        )

    def test_watchdog_source_has_no_miner_or_action_authority_imports(self) -> None:
        source = Path("tools/monitor_watchdog.py").read_text(encoding="utf-8")
        lowered = source.lower()
        for forbidden in (
            "miner_monitor",
            "hashcore",
            "read_summary",
            "run_hashcore",
            "reboot_miner",
            "192.168.",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
