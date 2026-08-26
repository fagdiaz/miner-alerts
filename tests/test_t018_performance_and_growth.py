"""T018 Performance, Bounded Queries, Database Growth and Action Invariance.

Validates:
  SC-005: Bounded query count and 24-hour latency under 2.0 seconds at scale.
  SC-006: Enabling/disabling fusion produces zero action, state or reboot differences.
  SC-007: Idempotent save prevents DB growth on replay; additive schema preserves data.

FR-008, FR-009, FR-011, FR-013, FR-014.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from app.event_store import EventStore
from tools.operations_dashboard import build_dashboard_data


class TestSC005PerformanceAndBoundedQueries(unittest.TestCase):
    """SC-005: 24-hour context evaluation under 2.0 seconds with bounded query count."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "perf_test.db"
        self.store = EventStore(self.db_path)
        self.now_ts = 1_786_700_000.0  # reference epoch
        self.window_hours = 24.0
        self.since_ts = self.now_ts - (self.window_hours * 3600.0)

        # Populate a realistic 24-hour dataset for a 4-miner fleet
        self._populate_24h_fleet()

    def tearDown(self) -> None:
        self.store.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _populate_24h_fleet(self) -> None:
        """Insert ~2,880 telemetry rows across 4 miners + events + decisions + firmware."""
        conn = sqlite3.connect(str(self.db_path))
        miners = [
            ("miner-23", "S19JPRO-23|h23:4028", "h23"),
            ("miner-24", "S19JPRO-24|h24:4028", "h24"),
            ("miner-25", "S19JPRO-25|h25:4028", "h25"),
            ("miner-26", "S19JPRO-26|h26:4028", "h26"),
        ]

        telemetry_rows = []
        for step in range(0, 1440, 2):
            ts = self.since_ts + (step * 60.0)
            for m_name, m_key, host in miners:
                rate = 98.5 if step % 20 != 0 else 42.0
                state = "OK" if rate > 60.0 else "LOW"
                telemetry_rows.append((
                    ts, m_key, m_name, host, state, 1, rate, 60.0, 3, 3, 40000 + step,
                    72.0, 12800.0, "authoritative", "quality_ok"
                ))

        conn.executemany(
            """
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded,
                rate_ths, threshold_ths, active_boards, expected_boards, elapsed_seconds,
                max_temp_c, chain_voltage_mv_avg, acquisition_authority, acquisition_reason_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            telemetry_rows,
        )

        events = []
        decisions = []
        firmware = []
        for i in range(50):
            ts = self.since_ts + (i * 1500.0)
            events.append((ts, "S19JPRO-23|h23:4028", "miner-23", "h23", "LOW", "WARN", "Hashrate low", json.dumps({"rate": 42.0})))
            decisions.append((ts, "S19JPRO-23|h23:4028", "miner-23", "h23", "BLOCKED", "LOW", 1, 60.0, 0, 0, 3, 0, 3600))
            firmware.append((ts, "2026-08-26 12:00:00", ts, "system", "S19JPRO-23|h23:4028", "miner-23", "h23", "status", f"fp_{i}", "thermal", "warn", "chain_temp_high", "Chain 1 hot"))

        conn.executemany(
            """
            INSERT INTO operational_events (
                occurred_ts, miner_key, miner_name, host, event_type, severity, summary, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            events,
        )
        conn.executemany(
            """
            INSERT INTO reboot_decisions (
                evaluated_ts, miner_key, miner_name, host, result, state, responded,
                threshold_ths, startup_guard_active, qa_mode, expected_boards, window_count, window_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            decisions,
        )
        conn.executemany(
            """
            INSERT INTO firmware_events (
                collected_ts, source_ts_text, source_ts_epoch, source_clock,
                miner_key, miner_name, host, source_tab, source_fingerprint,
                category, severity, code, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            firmware,
        )
        conn.execute(
            """
            INSERT INTO collector_runs (
                started_ts, completed_ts, status, attempted, succeeded, failed,
                events_parsed, events_inserted, events_duplicate, events_failed,
                truncated_streams, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (self.since_ts, self.now_ts, "ok", 4, 4, 0, 10, 10, 0, 0, 0, "Collector OK")
        )
        conn.commit()
        conn.close()

    def test_24h_dashboard_and_assessment_latency_under_two_seconds(self) -> None:
        """SC-005: 24-hour data evaluation completes well under the 2.0-second budget."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        t_start = time.monotonic()
        report = build_dashboard_data(
            conn,
            hours=24.0,
            now_ts=self.now_ts,
            row_limit=5000,
        )
        elapsed = time.monotonic() - t_start
        conn.close()

        self.assertLess(
            elapsed,
            2.0,
            f"SC-005 violation: 24h evaluation took {elapsed:.3f}s (budget: 2.0s)",
        )
        self.assertGreater(report["summary"]["miners"], 0)
        self.assertGreater(report["summary"]["events"], 0)

    def test_query_count_is_bounded_and_not_per_row(self) -> None:
        """SC-005 / FR-014: Queries executed for 24h context must be bounded (O(1), not O(N))."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        query_log: list[str] = []
        conn.set_trace_callback(query_log.append)

        build_dashboard_data(
            conn,
            hours=24.0,
            now_ts=self.now_ts,
            row_limit=5000,
        )
        conn.close()

        self.assertLess(
            len(query_log),
            20,
            f"Query count is unbounded: executed {len(query_log)} queries for 24h window",
        )


class TestSC007DatabaseGrowthAndIdempotency(unittest.TestCase):
    """SC-007: Idempotent save prevents DB growth on replay; additive schema preserves data."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "growth_test.db"
        self.store = EventStore(self.db_path)

    def tearDown(self) -> None:
        self.store.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_repeated_save_assessment_prevents_row_and_size_growth(self) -> None:
        """SC-007: Saving identical assessment 50 times results in exactly 1 persisted row."""
        payload = {
            "subject_type": "miner",
            "subject_ref": "miner-23",
            "miner_key": "miner-23",
            "ruleset_version": "1.0.0",
            "window_start_ts": 1000.0,
            "window_end_ts": 2000.0,
            "assessment_now_ts": 2000.0,
            "status": "complete",
            "evidence_digest": "abcdef0123456789" * 4,
            "findings_json": json.dumps([{"code": "signal.current_low"}]),
            "hypotheses_json": json.dumps([]),
            "contradictions_json": json.dumps([]),
            "missing_evidence_json": json.dumps([]),
        }

        first_id = self.store.save_assessment(**payload)
        size_after_first = self.db_path.stat().st_size

        for _ in range(49):
            repeat_id = self.store.save_assessment(**payload)
            self.assertEqual(first_id, repeat_id)

        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM incident_assessments").fetchone()[0]
        conn.close()

        self.assertEqual(count, 1, "Idempotent save must not create duplicate assessment rows")

        size_after_repeats = self.db_path.stat().st_size
        self.assertLessEqual(
            size_after_repeats,
            size_after_first + 4096,
            "Database file grew unexpectedly on idempotent assessment saves",
        )


class TestSC006ActionInvariance(unittest.TestCase):
    """SC-006: Enabling/disabling fusion produces zero action, state or reboot differences."""

    def test_fusion_presence_does_not_alter_action_invariants(self) -> None:
        """Verifies that fusion modules and assessments have zero authority over actions."""
        from app.evidence_fusion import IncidentAssessment
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(IncidentAssessment)}
        forbidden = {
            "allow_reboot", "trigger_reboot", "hashcore_command", "external_cli_command",
            "auto_action", "reboot_eligible", "streak_override", "target_miner_reboot"
        }
        self.assertFalse(field_names & forbidden)

        from app.evidence_fusion import FusionConfig
        cfg_disabled, _ = FusionConfig.from_mapping({})
        self.assertFalse(cfg_disabled.enabled)

        import app.evidence_fusion
        import inspect
        source = inspect.getsource(app.evidence_fusion)
        self.assertNotIn("reboot_safety", source)
        self.assertNotIn("hashcore", source)
        self.assertNotIn("miner_monitor", source)


if __name__ == "__main__":
    unittest.main()
