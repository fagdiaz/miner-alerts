import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.event_store import EventStore
from tools.incident_report import build_report, open_read_only, render_markdown


class IncidentReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "events.db"
        self.store = EventStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_report_correlates_samples_events_and_decisions(self) -> None:
        telemetry = {
            "max_temp_c": 78.0,
            "chain_voltage_mv_avg": 12825.0,
            "chain_power_w_total": 2698.0,
        }
        self.store.record_sample(
            observed_ts=9_900.0,
            miner_key="S19JPRO-23|h23:4028",
            miner_name="23",
            host="h23",
            state="LOW",
            responded=True,
            rate_ths=50.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=50_000,
            telemetry=telemetry,
        )
        self.store.record_event(
            occurred_ts=9_950.0,
            miner_key="S19JPRO-23|h23:4028",
            miner_name="23",
            host="h23",
            event_type="state_transition",
            severity="warning",
            summary="OK -> LOW",
        )
        self.store.record_reboot_decision(
            evaluated_ts=9_960.0,
            miner_key="S19JPRO-23|h23:4028",
            miner_name="23",
            host="h23",
            result="not_sustained",
            state="LOW",
            responded=True,
            rate_ths=50.0,
            threshold_ths=60.0,
            low_elapsed_seconds=60.0,
            active_boards=3,
            expected_boards=3,
            startup_guard_active=False,
            qa_mode=False,
            cooldown_remaining_seconds=None,
            window_count=0,
            window_seconds=21_600,
            telemetry=telemetry,
        )
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_report(connection, hours=1, miner="23", now_ts=10_000.0)
        finally:
            connection.close()

        self.assertEqual({"samples": 1, "events": 1, "decisions": 1}, report["counts"])
        self.assertEqual({"LOW": 1}, report["state_counts"])
        self.assertEqual({"not_sustained": 1}, report["decision_counts"])
        markdown = render_markdown(report)
        self.assertIn("12825.00 mV", markdown)
        self.assertIn("not AC input voltage", markdown)

    def test_read_only_connection_cannot_write(self) -> None:
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM operational_events")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
