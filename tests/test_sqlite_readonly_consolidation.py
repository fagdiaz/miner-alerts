import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.event_store import (
    EventStore,
    create_readonly_connection,
    open_readonly_connection,
    execute_readonly_with_retry,
)
from app.governance.energy_efficiency import fetch_latest_efficiency_assessments
from app.governance.fan_health import fetch_latest_cooling_assessments
from app.governance.preset_balancer import extract_miner_stability_metrics, analyze_elevator_sensitivity
from app.telegram.charts import fetch_miner_chart_data
from app.telegram.daily_digest import fetch_daily_digest_metrics
from app.vnish.presets import fetch_latest_preset_assessments


class TestSQLiteReadonlyConsolidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_events.db"
        self.store = EventStore(self.db_path)

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self.temp_dir.cleanup()

    def test_open_readonly_connection_nonexistent(self):
        non_existent = Path(self.temp_dir.name) / "does_not_exist.db"
        conn = open_readonly_connection(non_existent)
        self.assertIsNone(conn)

    def test_open_readonly_connection_pragmas(self):
        conn = open_readonly_connection(self.db_path)
        self.assertIsNotNone(conn)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA query_only;")
            query_only = cur.fetchone()[0]
            self.assertEqual(query_only, 1)

            # Assert write fails
            with self.assertRaises(sqlite3.OperationalError):
                cur.execute("CREATE TABLE attempt_write (id INT);")
        finally:
            conn.close()

    def test_execute_readonly_with_retry_eventual_success(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [
            sqlite3.OperationalError("database is locked"),
            sqlite3.OperationalError("database table is locked: busy"),
            "success_cursor",
        ]
        res = execute_readonly_with_retry(mock_cursor, "SELECT 1", max_retries=3, initial_backoff=0.01)
        self.assertEqual(res, "success_cursor")
        self.assertEqual(mock_cursor.execute.call_count, 3)

    def test_execute_readonly_with_retry_exhausted(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.OperationalError("database is locked")
        with self.assertRaises(sqlite3.OperationalError):
            execute_readonly_with_retry(mock_cursor, "SELECT 1", max_retries=2, initial_backoff=0.01)
        self.assertEqual(mock_cursor.execute.call_count, 3)

    def test_consumer_modules_graceful_with_consolidated_connection(self):
        miners = [{"name": "S19JPRO-01", "host": "192.168.1.100", "port": 4028}]
        
        # Test fan health
        cooling = fetch_latest_cooling_assessments(self.db_path, miners)
        self.assertIsInstance(cooling, list)

        # Test energy efficiency
        eff = fetch_latest_efficiency_assessments(self.db_path, miners)
        self.assertIsInstance(eff, list)

        # Test preset balancer
        stability = extract_miner_stability_metrics(self.db_path, miners, {})
        self.assertIsInstance(stability, list)

        # Test preset balancer cascade sensitivity
        sensitivity = analyze_elevator_sensitivity(stability, db_path=self.db_path)
        self.assertIsInstance(sensitivity, dict)

        # Test daily digest
        digest = fetch_daily_digest_metrics(self.db_path, miners=miners)
        self.assertIsInstance(digest, dict)
        self.assertIn("total_samples", digest)

        # Test charts
        chart = fetch_miner_chart_data(self.db_path, "S19JPRO-01")
        self.assertIsInstance(chart, dict)
        self.assertEqual(chart["count"], 0)

        # Test presets
        presets = fetch_latest_preset_assessments(self.db_path, miners)
        self.assertIsInstance(presets, list)


if __name__ == "__main__":
    unittest.main()
