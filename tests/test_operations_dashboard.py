import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.event_store import EventStore
from tools.operations_dashboard import (
    build_dashboard_data,
    generate_dashboard,
    open_read_only,
    render_dashboard_html,
)


class OperationsDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "miner alerts.db"
        self.store = EventStore(self.db_path)
        self.now_ts = 10_000.0

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def _record_fixture(self) -> None:
        telemetry = {
            "max_temp_c": 78.0,
            "chain_voltage_mv_avg": 12_825.0,
            "chain_power_w_total": 2_698.0,
            "frequency_mhz_avg": 515.0,
            "hw_errors_total": 2,
            "fan_rpm_max": 6_000,
            "fan_pwm_percent": 90.0,
            "diagnostic_flags": ["hw_errors_present"],
        }
        quality_points = (
            (9_400.0, 82.0, 1_000, 5, 2, 2),
            (9_700.0, 54.0, 1_090, 15, 7, 20),
            (9_990.0, 48.0, 1_180, 25, 12, 25),
        )
        for observed_ts, rate, accepted, rejected, stale, hw_errors in quality_points:
            self.store.record_sample(
                observed_ts=observed_ts,
                miner_key="S19JPRO-23|h23:4028",
                miner_name="<Miner 23>",
                host="h23",
                state="LOW",
                responded=True,
                rate_ths=rate,
                threshold_ths=60.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=int(40_000 + observed_ts),
                telemetry={
                    **telemetry,
                    "accepted_shares_total": accepted,
                    "rejected_shares_total": rejected,
                    "stale_shares_total": stale,
                    "hw_errors_total": hw_errors,
                    "chain_fault_count": 0,
                    "chains_not_mining_count": 0,
                    "chains_transitioning_count": 0,
                    "quality_flags": [],
                },
            )
        self.store.record_sample(
            observed_ts=9_980.0,
            miner_key="S19JPRO-24|h24:4028",
            miner_name="Miner 24",
            host="h24",
            state="OK",
            responded=True,
            rate_ths=99.5,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=70_000,
            telemetry={"max_temp_c": 75.0},
        )
        self.store.record_event(
            occurred_ts=9_995.0,
            miner_key="S19JPRO-23|h23:4028",
            miner_name="<Miner 23>",
            host="h23",
            event_type="state_transition",
            severity="warning",
            previous_state="OK",
            new_state="LOW",
            rate_ths=48.0,
            threshold_ths=60.0,
            summary="<script>alert('x')</script>",
        )
        self.store.record_reboot_decision(
            evaluated_ts=9_996.0,
            miner_key="S19JPRO-23|h23:4028",
            miner_name="<Miner 23>",
            host="h23",
            result="fleet_incident",
            state="LOW",
            responded=True,
            rate_ths=48.0,
            threshold_ths=60.0,
            low_elapsed_seconds=700.0,
            active_boards=3,
            expected_boards=3,
            startup_guard_active=False,
            qa_mode=False,
            cooldown_remaining_seconds=None,
            window_count=0,
            window_seconds=21_600,
            telemetry=telemetry,
            details={"affected_count": 2},
        )
        self.store.record_firmware_event(
            collected_ts=9_997.0,
            source_ts_text="2025/09/08 08:51:59",
            miner_key="S19JPRO-23|h23:4028",
            miner_name="<Miner 23>",
            host="h23",
            source_tab="status",
            source_fingerprint="b" * 64,
            category="restart",
            severity="warning",
            code="watchdog_chain_restart",
            summary="Reinicio interno por corte de cadena",
        )

    def test_builds_bounded_fleet_view_model(self) -> None:
        self._record_fixture()
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(
                connection,
                hours=24.0,
                now_ts=self.now_ts,
                stale_after_seconds=900.0,
                row_limit=100,
            )
        finally:
            connection.close()

        self.assertEqual(2, report["summary"]["miners"])
        self.assertEqual(1, report["summary"]["healthy"])
        self.assertEqual(1, report["summary"]["degraded"])
        self.assertEqual(1, report["summary"]["events"])
        self.assertEqual(1, report["summary"]["decisions"])
        self.assertEqual(1, report["summary"]["firmware_events"])
        self.assertEqual("watchdog_chain_restart", report["firmware_events"][0]["code"])
        self.assertEqual("<Miner 23>", report["miners"][0]["miner_name"])
        self.assertEqual("Miner 24", report["miners"][1]["miner_name"])
        self.assertEqual([82.0, 54.0, 48.0], report["miners"][0]["rate_history"])
        self.assertEqual("fleet_incident", report["miners"][0]["latest_decision"])
        self.assertEqual("critical", report["miners"][0]["stability"]["status"])
        self.assertIn(
            "rate_below_threshold",
            report["miners"][0]["stability"]["reason_codes"],
        )
        self.assertEqual("learning", report["miners"][1]["stability"]["status"])
        self.assertEqual(1, report["stability_counts"]["critical"])
        self.assertEqual(1, report["stability_counts"]["learning"])
        self.assertEqual("watch", report["miners"][0]["quality"]["status"])
        self.assertIn(
            "rejected_share_rate",
            report["miners"][0]["quality"]["reason_codes"],
        )
        self.assertEqual("learning", report["miners"][1]["quality"]["status"])
        self.assertEqual(1, report["quality_counts"]["watch"])
        self.assertEqual(1, report["quality_counts"]["learning"])

    def test_html_is_self_contained_responsive_and_escaped(self) -> None:
        self._record_fixture()
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        rendered = render_dashboard_html(report, title="Miner Alerts Ops")

        self.assertIn("<!doctype html>", rendered.lower())
        self.assertIn('name="viewport"', rendered)
        self.assertIn("<svg", rendered)
        self.assertIn("Stability Advisor", rendered)
        self.assertIn("Mining Quality", rendered)
        self.assertIn("Vnish Firmware Timeline", rendered)
        self.assertIn("watchdog_chain_restart", rendered)
        self.assertIn("Shares rechazadas", rendered)
        self.assertIn("CRITICAL", rendered)
        self.assertIn("LEARNING", rendered)
        self.assertIn("&lt;Miner 23&gt;", rendered)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", rendered)
        self.assertNotIn("<script>alert", rendered)
        self.assertNotIn("https://", rendered)
        self.assertNotIn("http://", rendered)

    def test_connection_is_read_only(self) -> None:
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE forbidden(id INTEGER)")
        finally:
            connection.close()

    def test_empty_store_generates_useful_page(self) -> None:
        self.store.close()
        output_path = Path(self.temp_dir.name) / "dashboard" / "index.html"

        result = generate_dashboard(
            self.db_path,
            output_path,
            hours=24.0,
            now_ts=self.now_ts,
        )

        self.assertEqual(output_path, result)
        rendered = output_path.read_text(encoding="utf-8")
        self.assertIn("Sin telemetria disponible", rendered)
        self.assertGreater(len(rendered), 1_000)

    def test_generator_has_no_monitor_network_or_mutating_sql_paths(self) -> None:
        source = Path("tools/operations_dashboard.py").read_text(encoding="utf-8")

        self.assertNotIn("miner_monitor", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("subprocess", source)
        self.assertIn("analyze_mining_quality", source)
        self.assertNotIn("INSERT INTO", source)
        self.assertNotIn("UPDATE ", source)
        self.assertNotIn("DELETE FROM", source)


if __name__ == "__main__":
    unittest.main()
