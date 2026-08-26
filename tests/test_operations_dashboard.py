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
        self.store.record_collector_run(
            started_ts=9_970.0,
            completed_ts=9_998.0,
            status="ok",
            attempted=16,
            succeeded=16,
            failed=0,
            events_parsed=1,
            events_inserted=1,
            events_duplicate=0,
            events_failed=0,
            truncated_streams=0,
            summary="Coleccion ok: 16/16 streams.",
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
        self.assertEqual("ok", report["collector_run"]["status"])
        self.assertEqual(2.0, report["collector_run"]["age_seconds"])
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
        self.assertIn("Collector Vnish", rendered)
        self.assertIn("16/16 streams", rendered)
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


# ---------------------------------------------------------------------------
# T015 — Spec 023: incident_assessments integration in operations_dashboard
# ---------------------------------------------------------------------------

class IncidentAssessmentsDashboardTests(unittest.TestCase):
    """Tests for T015: shared renderer integration in operations_dashboard.

    FR-011: assessments are displayed from stored rows only.
    No scoring, no hypothesis re-computation, no inference.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "assess_test.db"
        self.store = EventStore(self.db_path)
        self.now_ts = 20_000.0

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def _save_assessment(self, subject_ref: str, status: str = "complete",
                         assessment_ts: float = 19_500.0) -> int:
        from app.evidence_fusion import RULESET_VERSION, compute_evidence_digest
        import json
        digest = compute_evidence_digest([], RULESET_VERSION)
        return self.store.save_assessment(
            subject_type="miner",
            subject_ref=subject_ref,
            miner_key=subject_ref,
            ruleset_version=RULESET_VERSION,
            window_start_ts=assessment_ts - 3600.0,
            window_end_ts=assessment_ts,
            assessment_now_ts=assessment_ts,
            status=status,
            evidence_digest=digest,
            findings_json=json.dumps([]),
            hypotheses_json=json.dumps([]),
            contradictions_json=json.dumps([]),
            missing_evidence_json=json.dumps([]),
        )

    # --- Data layer tests ---

    def test_incident_assessments_key_present_in_report(self) -> None:
        """build_dashboard_data must include 'incident_assessments' in its output."""
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()
        self.assertIn("incident_assessments", report)

    def test_assessments_count_in_summary(self) -> None:
        """summary['assessments'] must equal the number of assessments in the window."""
        self._save_assessment("miner1|h1:4028", assessment_ts=19_500.0)
        self._save_assessment("miner2|h2:4028", assessment_ts=19_800.0)
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        self.assertEqual(2, report["summary"]["assessments"])
        self.assertEqual(2, len(report["incident_assessments"]))

    def test_assessments_bounded_by_since_ts(self) -> None:
        """Assessments outside the time window must not appear."""
        # This assessment is 25 hours before now_ts → outside 24h window
        self._save_assessment("miner1|h1:4028", assessment_ts=self.now_ts - 25 * 3600.0)
        # This one is inside the window
        self._save_assessment("miner2|h2:4028", assessment_ts=self.now_ts - 1.0)
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        self.assertEqual(1, report["summary"]["assessments"])
        self.assertEqual("miner2|h2:4028", report["incident_assessments"][0]["subject_ref"])

    def test_assessments_ordered_newest_first(self) -> None:
        """Assessments must be returned newest-first."""
        self._save_assessment("miner1|h1:4028", assessment_ts=19_000.0)
        self._save_assessment("miner2|h2:4028", assessment_ts=19_900.0)
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        rows = report["incident_assessments"]
        self.assertEqual(2, len(rows))
        # Newest first
        self.assertGreaterEqual(
            rows[0]["assessment_now_ts"],
            rows[1]["assessment_now_ts"],
        )

    def test_no_assessments_returns_empty_list(self) -> None:
        """When incident_assessments table is empty, must return [] without error."""
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        self.assertEqual([], report["incident_assessments"])
        self.assertEqual(0, report["summary"]["assessments"])

    # --- HTML rendering tests ---

    def test_html_contains_assessment_section_header(self) -> None:
        """render_dashboard_html must include the Evaluaciones de incidente section."""
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        rendered = render_dashboard_html(report)
        self.assertIn("Evaluaciones de incidente", rendered)
        self.assertIn("Lectura / sin accion automatica", rendered)

    def test_html_assessment_row_shows_stored_fields(self) -> None:
        """When an assessment exists, HTML must show subject_ref, status, and ruleset_version."""
        from app.evidence_fusion import RULESET_VERSION
        self._save_assessment("miner1|h1:4028", status="complete", assessment_ts=19_500.0)
        self.store.close()

        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        rendered = render_dashboard_html(report)
        self.assertIn("miner1|h1:4028", rendered)
        self.assertIn("complete", rendered)
        self.assertIn(RULESET_VERSION, rendered)

    def test_html_empty_assessment_section_graceful(self) -> None:
        """With no assessments in range, HTML must show empty-cell message."""
        self.store.close()
        connection = open_read_only(self.db_path)
        try:
            report = build_dashboard_data(connection, hours=24.0, now_ts=self.now_ts)
        finally:
            connection.close()

        rendered = render_dashboard_html(report)
        self.assertIn("Sin evaluaciones en la ventana", rendered)

    # --- FR-011 invariant: no re-scoring, no re-inference ---

    def test_fr011_no_scoring_imports_in_render_path(self) -> None:
        """operations_dashboard.py must not import evidence_fusion for scoring.
        It may only use the renderer (render_assessment_text/telegram) or display
        stored fields — but since we pass rows directly, no import is needed at all."""
        source = Path("tools/operations_dashboard.py").read_text(encoding="utf-8")
        # The dashboard must NOT call any scoring/hypothesis functions
        self.assertNotIn("evaluate_hypothesis", source)
        self.assertNotIn("compute_confidence_ceiling", source)
        self.assertNotIn("max_cause_level", source)
        self.assertNotIn("detect_fleet_pattern", source)
        # The dashboard reads stored rows — no IncidentAssessment construction
        self.assertNotIn("IncidentAssessment(", source)

    def test_known_tables_includes_incident_assessments(self) -> None:
        """_KNOWN_TABLES allowlist must include 'incident_assessments'."""
        from tools.operations_dashboard import _KNOWN_TABLES
        self.assertIn("incident_assessments", _KNOWN_TABLES)


if __name__ == "__main__":
    unittest.main()
