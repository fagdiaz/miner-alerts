"""Benchmark and latency certification for Spec 069 SQLite queries (RF-01).

Certifies that windowed read-only telemetry queries over chain_telemetry_samples
execute in < 15 ms with the composite index ix_chain_telemetry_miner_chain_time.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from app.core.event_store import EventStore, fetch_chain_samples_window


class TestChainQueryPerformance(unittest.TestCase):
    """Certifies query execution latency under 10,000 synthetic records (Spec 069)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_perf.db"
        self.store = EventStore(self.db_path)
        self.assertTrue(self.store.available)

        # Seed 10,000 synthetic records
        # 10 miners x 3 chains x ~334 ticks
        now = time.time()
        conn = self.store._connection
        with self.store._lock:
            rows_to_insert = []
            sensor_err_json = json.dumps([{"state": "error", "board": 39, "chip": 54, "loc": 28}])
            sensor_ok_json = json.dumps([{"state": "measure", "board": 39, "chip": 54, "loc": 28}])

            total_records = 10000
            for i in range(total_records):
                miner_id = (i % 10) + 1
                miner_key = f"S19JPRO-{miner_id}"
                chain_id = i % 3
                ts = now - ((total_records - i) * 60.0)  # 1 minute apart
                has_err = 1 if (miner_id == 24 and chain_id == 2) else 0
                s_json = sensor_err_json if has_err else sensor_ok_json
                rows_to_insert.append((
                    ts,
                    miner_key,
                    chain_id,
                    "mining",
                    30000.0,
                    30000.0,
                    0.0,
                    525.0,
                    has_err,
                    s_json,
                    126,
                    0,
                    0,
                    0,
                ))

            conn.executemany(
                """
                INSERT INTO chain_telemetry_samples (
                    observed_ts, miner_key, chain_id, state,
                    hr_realtime, hr_nominal, hr_deficit_pct, freq_avg,
                    sensors_error_count, sensors_json, chips_total,
                    chips_error_count, chips_throttled_count, chips_hw_errors_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )
            conn.commit()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_composite_index_usage_explain_query_plan(self):
        """Verify that SQLite optimizer uses ix_chain_telemetry_miner_chain_time."""
        conn = self.store._connection
        with self.store._lock:
            cur = conn.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT observed_ts, sensors_error_count, sensors_json, hr_deficit_pct, chips_error_count
                FROM chain_telemetry_samples
                WHERE miner_key = ? AND chain_id = ? AND observed_ts >= ?
                ORDER BY observed_ts ASC
                """,
                ("S19JPRO-1", 1, time.time() - 43200.0),
            )
            plan = cur.fetchall()
            plan_text = " ".join(str(list(step)) for step in plan)
            self.assertIn("ix_chain_telemetry_miner_chain_time", plan_text)

    def test_window_query_latency_under_15ms(self):
        """RF-01: Certify that window queries take < 15 ms across 50 iterations."""
        since_ts = time.time() - 43200.0  # 12 hour window
        iterations = 50

        # Warm up cache
        _ = self.store.fetch_chain_samples_window("S19JPRO-1", 1, since_ts)

        latencies_ms = []
        for i in range(iterations):
            miner_key = f"S19JPRO-{(i % 10) + 1}"
            chain_id = i % 3
            t0 = time.perf_counter()
            samples = self.store.fetch_chain_samples_window(miner_key, chain_id, since_ts)
            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000.0
            latencies_ms.append(elapsed_ms)
            self.assertIsInstance(samples, list)

        avg_ms = sum(latencies_ms) / len(latencies_ms)
        max_ms = max(latencies_ms)

        # Certification assertions
        self.assertLess(avg_ms, 15.0, f"Average query latency {avg_ms:.2f}ms exceeded 15ms ceiling")
        self.assertLess(max_ms, 35.0, f"Peak query latency {max_ms:.2f}ms exceeded tolerance")

    def test_standalone_helper_fetch_chain_samples_window(self):
        """Test the top-level fetch_chain_samples_window helper with connection and path."""
        since_ts = time.time() - 43200.0

        # Via EventStore
        res_store = fetch_chain_samples_window(self.store, "S19JPRO-2", 0, since_ts)
        self.assertIsInstance(res_store, list)
        self.assertGreater(len(res_store), 0)

        # Via db_path string
        res_path = fetch_chain_samples_window(str(self.db_path), "S19JPRO-2", 0, since_ts)
        self.assertIsInstance(res_path, list)
        self.assertEqual(len(res_store), len(res_path))


if __name__ == "__main__":
    unittest.main()
