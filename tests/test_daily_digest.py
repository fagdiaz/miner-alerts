"""Unit tests for Daily Executive Digest (Spec 034)."""

from __future__ import annotations

import datetime
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.daily_digest import (
    is_digest_due,
    inspect_latest_backup,
    fetch_daily_digest_metrics,
    format_daily_digest,
    ARGENTINA_TZ,
)


class TestDailyDigestScheduling(unittest.TestCase):
    def test_is_digest_due_before_target(self):
        dt = datetime.datetime(2026, 9, 8, 7, 59, 0, tzinfo=ARGENTINA_TZ)
        self.assertFalse(is_digest_due(dt, target_time_str="08:00", last_sent_date=None))

    def test_is_digest_due_at_or_after_target(self):
        dt = datetime.datetime(2026, 9, 8, 8, 0, 0, tzinfo=ARGENTINA_TZ)
        self.assertTrue(is_digest_due(dt, target_time_str="08:00", last_sent_date=None))

        dt_later = datetime.datetime(2026, 9, 8, 11, 30, 0, tzinfo=ARGENTINA_TZ)
        self.assertTrue(is_digest_due(dt_later, target_time_str="08:00", last_sent_date=None))

    def test_is_digest_due_already_sent_today(self):
        dt = datetime.datetime(2026, 9, 8, 8, 30, 0, tzinfo=ARGENTINA_TZ)
        # Already sent today
        self.assertFalse(is_digest_due(dt, target_time_str="08:00", last_sent_date="2026-09-08"))
        # Sent yesterday -> should be due today!
        self.assertTrue(is_digest_due(dt, target_time_str="08:00", last_sent_date="2026-09-07"))

    def test_is_digest_due_custom_time(self):
        dt = datetime.datetime(2026, 9, 8, 9, 15, 0, tzinfo=ARGENTINA_TZ)
        self.assertFalse(is_digest_due(dt, target_time_str="09:30", last_sent_date=None))

        dt_after = datetime.datetime(2026, 9, 8, 9, 45, 0, tzinfo=ARGENTINA_TZ)
        self.assertTrue(is_digest_due(dt_after, target_time_str="09:30", last_sent_date=None))


class TestDailyDigestBackupInspection(unittest.TestCase):
    def test_inspect_missing_backup_root(self):
        res = inspect_latest_backup("non_existent_backups_dir_12345")
        self.assertFalse(res["verified"])

    def test_inspect_valid_backup_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_root = Path(tmpdir)
            verified_dir = backup_root / "verified" / "20260908T030000Z_abcd"
            verified_dir.mkdir(parents=True)

            manifest = {
                "file_size_bytes": 24_326_963,
                "integrity_check": "ok",
                "start_iso": "2026-09-08T06:00:00+00:00",  # 03:00 in Argentina UTC-3
            }
            (verified_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            res = inspect_latest_backup(backup_root)
            self.assertTrue(res["verified"])
            self.assertAlmostEqual(res["size_mb"], 23.2, delta=0.5)
            self.assertEqual(res["time_str"], "03:00")


class TestDailyDigestMetricsAndFormatting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_digest.db"
        self._init_sqlite()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_sqlite(self):
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE telemetry_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_ts REAL NOT NULL,
                miner_key TEXT NOT NULL,
                miner_name TEXT NOT NULL,
                host TEXT NOT NULL,
                state TEXT NOT NULL,
                responded INTEGER NOT NULL,
                rate_ths REAL,
                threshold_ths REAL NOT NULL,
                active_boards INTEGER,
                expected_boards INTEGER NOT NULL,
                elapsed_seconds INTEGER,
                max_temp_c REAL,
                chain_voltage_mv_avg REAL,
                chain_power_w_total REAL,
                frequency_mhz_avg REAL,
                hw_errors_total INTEGER,
                fan_rpm_max INTEGER,
                fan_pwm_percent REAL,
                diagnostic_flags_json TEXT NOT NULL DEFAULT '[]',
                accepted_shares_total INTEGER,
                rejected_shares_total INTEGER,
                stale_shares_total INTEGER,
                chain_fault_count INTEGER,
                chains_not_mining_count INTEGER,
                chains_transitioning_count INTEGER,
                quality_flags_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE operational_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_ts REAL NOT NULL,
                miner_key TEXT,
                miner_name TEXT,
                host TEXT,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                classification TEXT,
                previous_state TEXT,
                new_state TEXT,
                rate_ths REAL,
                threshold_ths REAL,
                previous_elapsed INTEGER,
                current_elapsed INTEGER,
                action_source TEXT,
                action_ts REAL,
                summary TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE reboot_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluated_ts REAL NOT NULL,
                miner_key TEXT NOT NULL,
                miner_name TEXT NOT NULL,
                host TEXT NOT NULL,
                result TEXT NOT NULL,
                state TEXT NOT NULL,
                responded INTEGER NOT NULL,
                rate_ths REAL
            );
            """
        )
        conn.commit()
        conn.close()

    def test_fetch_metrics_empty_db(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028, "threshold_ths": 100.0},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028, "threshold_ths": 100.0},
        ]
        metrics = fetch_daily_digest_metrics(self.db_path, miners, now_ts=10000.0)
        self.assertEqual(metrics["total_samples"], 0)
        self.assertEqual(metrics["nominal_hashrate_ths"], 200.0)
        self.assertEqual(metrics["incidents_24h"], 0)
        self.assertEqual(metrics["reboots_24h"], 0)

        formatted = format_daily_digest(metrics, date_str="08/09/2026")
        self.assertIn("Reporte Diario", formatted)
        self.assertIn("08/09/2026", formatted)
        self.assertIn("Uptime Flota", formatted)

    def test_fetch_metrics_with_telemetry(self):
        now_ts = 100_000.0
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()

        # Insert 10 samples for miner 23: 100 TH/s, 2800 W (28.0 J/TH), OK
        for i in range(10):
            ts = now_ts - (i * 3600)  # over last 10 hours
            cur.execute(
                """
                INSERT INTO telemetry_samples (
                    observed_ts, miner_key, miner_name, host, state, responded,
                    rate_ths, threshold_ths, active_boards, expected_boards,
                    chain_power_w_total, accepted_shares_total, rejected_shares_total, hw_errors_total
                ) VALUES (?, 'k23', 'S19JPRO-23', '192.168.1.23', 'OK', 1, 100.0, 95.0, 3, 3, 2800.0, ?, ?, 5)
                """,
                (ts, 1000 + (i * 100), 2 + (i * 1)),
            )

        # Insert 10 samples for miner 24: 102 TH/s, 2652 W (26.0 J/TH), OK
        for i in range(10):
            ts = now_ts - (i * 3600)
            cur.execute(
                """
                INSERT INTO telemetry_samples (
                    observed_ts, miner_key, miner_name, host, state, responded,
                    rate_ths, threshold_ths, active_boards, expected_boards,
                    chain_power_w_total, accepted_shares_total, rejected_shares_total, hw_errors_total
                ) VALUES (?, 'k24', 'S19JPRO-24', '192.168.1.24', 'OK', 1, 102.0, 95.0, 3, 3, 2652.0, 500, 1, 0)
                """,
                (ts,),
            )

        # Insert 1 warning event
        cur.execute(
            """
            INSERT INTO operational_events (occurred_ts, event_type, severity, summary)
            VALUES (?, 'irregular_episode', 'warning', 'Low hashrate detected')
            """,
            (now_ts - 5000,),
        )

        conn.commit()
        conn.close()

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028, "threshold_ths": 95.0},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028, "threshold_ths": 95.0},
        ]
        metrics = fetch_daily_digest_metrics(self.db_path, miners, now_ts=now_ts)

        self.assertEqual(metrics["total_samples"], 20)
        self.assertEqual(metrics["fleet_uptime_pct"], 100.0)
        self.assertAlmostEqual(metrics["avg_hashrate_ths"], 202.0, delta=0.5)
        self.assertAlmostEqual(metrics["nominal_hashrate_ths"], 190.0, delta=0.5)
        self.assertIsNotNone(metrics["avg_efficiency_j_th"])
        self.assertAlmostEqual(metrics["avg_efficiency_j_th"], 27.0, delta=1.5)
        self.assertEqual(metrics["incidents_24h"], 1)

        formatted = format_daily_digest(metrics, date_str="08/09/2026")
        self.assertIn("202.0 TH/s", formatted)
        self.assertIn("1 anomalías", formatted)
        self.assertIn("J/TH", formatted)


class TestDailyDigestIntegration(unittest.TestCase):
    def test_digest_state_persistence(self):
        from app.miner_monitor import save_state, load_state, MinerState

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            states = {"m1": MinerState()}
            save_state(state_file, states, last_update_id=10, last_daily_digest_date="2026-09-08")

            raw = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(raw.get("last_daily_digest_date"), "2026-09-08")

            loaded_states, last_id = load_state(state_file)
            self.assertEqual(last_id, 10)

    def test_digest_benchmark_on_real_db_if_present(self):
        real_db = Path("data/miner_alerts.db")
        if not real_db.exists():
            return
        import time
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "threshold_ths": 100.0},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "threshold_ths": 100.0},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "threshold_ths": 100.0},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "threshold_ths": 100.0},
        ]
        t0 = time.perf_counter()
        metrics = fetch_daily_digest_metrics(real_db, miners)
        t_query = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        card = format_daily_digest(metrics)
        t_format = (time.perf_counter() - t1) * 1000.0

        self.assertLess(t_query, 1500.0, f"Query took {t_query:.1f}ms, expected < 1500ms")
        self.assertIn("Reporte Diario", card)


if __name__ == "__main__":
    unittest.main()

