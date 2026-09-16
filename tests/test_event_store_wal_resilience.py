"""Unit and integration tests for Spec 061 — SQLite WAL resilience and integrity.

Covers:
- Asynchronous quick-check daemon thread in startup
- Automatic corruption quarantine and clean DB recreation with schema v7
- Soft ceiling max_page_count = 262144 (~1 GB)
- EventStore.checkpoint_wal (PASSIVE, TRUNCATE, FULL, RESTART)
- create_readonly_connection and execute_readonly_with_retry handling BUSY_SNAPSHOT
- Multi-reader concurrency under continuous write and TRUNCATE checkpoint
"""

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from app.core.event_store import (
    SCHEMA_VERSION,
    EventStore,
    _is_busy_or_snapshot_error,
    create_readonly_connection,
    execute_readonly_with_retry,
)


class EventStoreWalResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "miner_alerts.db"
        self.errors: list[str] = []
        self.store: Optional[EventStore] = None

    def tearDown(self) -> None:
        if self.store is not None:
            try:
                self.store.close()
            except Exception:
                pass
            self.store = None
        self.temp_dir.cleanup()

    def test_async_integrity_check_clean_db(self) -> None:
        """On a healthy database, async integrity check completes cleanly without errors."""
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        completed = self.store.wait_for_integrity_check(timeout=5.0)
        self.assertTrue(completed, "Integrity check timed out")
        self.assertTrue(self.store.integrity_checked)
        self.assertFalse(self.store.integrity_failed)
        self.assertIsNone(self.store.integrity_quarantine_path)
        self.assertEqual([], self.errors)

    def test_max_page_count_configured(self) -> None:
        """EventStore sets PRAGMA max_page_count = 262144 (~1 GB)."""
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        with self.store._lock:
            row = self.store._connection.execute("PRAGMA max_page_count;").fetchone()
        self.assertEqual(262144, int(row[0]))

    def test_quarantine_and_recreate_on_corrupt_database(self) -> None:
        """Corrupt database file is quarantined to miner_alerts_corrupt_<epoch>.db and clean DB recreated."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_bytes(b"CORRUPT_NON_SQLITE_DATA_HEADER_PAGES_GARBAGE" * 20)

        self.store = EventStore(self.db_path, on_error=self.errors.append)
        self.store.wait_for_integrity_check(timeout=5.0)
        self.assertTrue(self.store.integrity_checked)
        self.assertTrue(self.store.integrity_failed)
        self.assertIsNotNone(self.store.integrity_quarantine_path)
        self.assertTrue(self.store.integrity_quarantine_path.exists())
        self.assertIn("corrupt", self.store.integrity_quarantine_path.name)

        # Active store is available and clean
        self.assertTrue(self.store.available)
        self.assertEqual(SCHEMA_VERSION, self.store.schema_version)

        # Store can record telemetry sample normally
        sample_id = self.store.record_sample(
            observed_ts=1000.0,
            miner_key="S19-01|10.0.0.1:4028",
            miner_name="S19-01",
            host="10.0.0.1",
            state="OK",
            responded=True,
            rate_ths=95.5,
            threshold_ths=90.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=120,
        )
        self.assertIsNotNone(sample_id)
        self.assertEqual(1, self.store.count_rows("telemetry_samples"))

    def test_quarantine_on_corrupt_page_async_worker(self) -> None:
        """Async worker detects corrupt page via PRAGMA quick_check, quarantines and recreates DB."""
        # 1. Create a valid database with schema and data
        init_store = EventStore(self.db_path, on_error=self.errors.append)
        for i in range(50):
            init_store.record_sample(
                observed_ts=1000.0 + i,
                miner_key="m1|10.0.0.1:4028",
                miner_name="m1",
                host="10.0.0.1",
                state="OK",
                responded=True,
                rate_ths=90.0,
                threshold_ths=90.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=120,
            )
        init_store.checkpoint_wal("TRUNCATE")
        init_store.close()

        # 2. Corrupt internal pages while leaving header intact
        with open(self.db_path, "r+b") as f:
            f.seek(4096)
            f.write(b"\xff" * 512)

        # 3. Open EventStore — async worker catches the malformed disk image
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        self.store.wait_for_integrity_check(timeout=5.0)

        self.assertTrue(self.store.integrity_checked)
        self.assertTrue(self.store.integrity_failed)
        self.assertIsNotNone(self.store.integrity_quarantine_path)
        self.assertTrue(self.store.integrity_quarantine_path.exists())
        self.assertTrue(self.store.available)
        self.assertEqual(SCHEMA_VERSION, self.store.schema_version)

    def test_checkpoint_wal_modes(self) -> None:
        """checkpoint_wal supports PASSIVE, FULL, RESTART, and TRUNCATE."""
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        for i in range(10):
            self.store.record_sample(
                observed_ts=1000.0 + i,
                miner_key=f"miner_{i}|10.0.0.{i}:4028",
                miner_name=f"miner_{i}",
                host=f"10.0.0.{i}",
                state="OK",
                responded=True,
                rate_ths=92.0,
                threshold_ths=90.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=120,
            )

        # PASSIVE checkpoint
        busy, log_frames, checkpointed = self.store.checkpoint_wal("PASSIVE")
        self.assertEqual(0, busy)
        self.assertGreaterEqual(log_frames, 0)
        self.assertGreaterEqual(checkpointed, 0)

        # TRUNCATE checkpoint
        busy, log_frames, checkpointed = self.store.checkpoint_wal("TRUNCATE")
        self.assertEqual(0, busy)
        self.assertEqual(0, log_frames)
        self.assertEqual(0, checkpointed)

        wal_path = Path(str(self.db_path) + "-wal")
        if wal_path.exists():
            self.assertEqual(0, wal_path.stat().st_size)

        # FULL and RESTART checkpoints
        busy, _, _ = self.store.checkpoint_wal("FULL")
        self.assertEqual(0, busy)
        busy, _, _ = self.store.checkpoint_wal("RESTART")
        self.assertEqual(0, busy)

        # Invalid mode raises ValueError
        with self.assertRaises(ValueError):
            self.store.checkpoint_wal("INVALID_MODE")

    def test_create_readonly_connection_enforces_read_only(self) -> None:
        """create_readonly_connection allows SELECT but forbids writes."""
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        self.store.record_sample(
            observed_ts=1000.0,
            miner_key="miner_01|10.0.0.1:4028",
            miner_name="miner_01",
            host="10.0.0.1",
            state="OK",
            responded=True,
            rate_ths=93.0,
            threshold_ths=90.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=120,
        )
        self.store.checkpoint_wal("PASSIVE")
        self.store.close()
        self.store = None

        ro_conn = create_readonly_connection(self.db_path)
        try:
            cursor = ro_conn.execute("SELECT COUNT(*) AS c FROM telemetry_samples")
            row = cursor.fetchone()
            self.assertEqual(1, row["c"])

            with self.assertRaises(sqlite3.OperationalError):
                ro_conn.execute("DELETE FROM telemetry_samples")
        finally:
            ro_conn.close()

    def test_create_readonly_connection_non_existent_file(self) -> None:
        """create_readonly_connection raises FileNotFoundError if db does not exist."""
        non_existent = Path(self.temp_dir.name) / "does_not_exist.db"
        with self.assertRaises(FileNotFoundError):
            create_readonly_connection(non_existent)

    def test_execute_readonly_with_retry_on_busy_snapshot(self) -> None:
        """execute_readonly_with_retry retries on snapshot lock error with backoff."""
        mock_cursor = MagicMock()
        attempts = 0

        def side_effect(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                err = sqlite3.OperationalError("database table is locked: snapshot")
                setattr(err, "sqlite_errorname", "SQLITE_BUSY_SNAPSHOT")
                setattr(err, "sqlite_errorcode", 517)
                raise err
            mock_res = MagicMock()
            mock_res.fetchall.return_value = [("success",)]
            return mock_res

        mock_cursor.execute.side_effect = side_effect

        result_cursor = execute_readonly_with_retry(
            mock_cursor,
            "SELECT 1",
            max_retries=3,
            initial_backoff=0.001,
        )
        self.assertEqual([("success",)], result_cursor.fetchall())
        self.assertEqual(3, attempts)

    def test_execute_readonly_with_retry_exceeds_max_retries(self) -> None:
        """execute_readonly_with_retry raises error when retries are exhausted."""
        mock_cursor = MagicMock()
        err = sqlite3.OperationalError("database table is locked: snapshot")
        setattr(err, "sqlite_errorname", "SQLITE_BUSY_SNAPSHOT")
        mock_cursor.execute.side_effect = err

        with self.assertRaises(sqlite3.OperationalError):
            execute_readonly_with_retry(
                mock_cursor,
                "SELECT 1",
                max_retries=2,
                initial_backoff=0.001,
            )

    def test_is_busy_or_snapshot_error_detection(self) -> None:
        """_is_busy_or_snapshot_error correctly detects lock and snapshot error variants."""
        err_snapshot = sqlite3.OperationalError("database table is locked: snapshot")
        self.assertTrue(_is_busy_or_snapshot_error(err_snapshot))

        err_locked = sqlite3.OperationalError("database is locked")
        self.assertTrue(_is_busy_or_snapshot_error(err_locked))

        err_busy = sqlite3.OperationalError("database is busy")
        self.assertTrue(_is_busy_or_snapshot_error(err_busy))

        err_other = sqlite3.OperationalError("no such table: foo")
        self.assertFalse(_is_busy_or_snapshot_error(err_other))

    def test_multi_reader_concurrency_with_continuous_writes_and_truncate(self) -> None:
        """Multiple readers query concurrently while writer inserts and performs TRUNCATE."""
        self.store = EventStore(self.db_path, on_error=self.errors.append)
        stop_event = threading.Event()
        writer_count = 0
        reader_counts = [0, 0, 0, 0]
        reader_errors: list[Exception] = []

        def writer_worker():
            nonlocal writer_count
            while not stop_event.is_set():
                writer_count += 1
                self.store.record_sample(
                    observed_ts=time.time(),
                    miner_key=f"m_{writer_count % 5}|10.0.0.1:4028",
                    miner_name=f"m_{writer_count % 5}",
                    host="10.0.0.1",
                    state="OK",
                    responded=True,
                    rate_ths=90.0 + (writer_count % 10),
                    threshold_ths=90.0,
                    active_boards=3,
                    expected_boards=3,
                    elapsed_seconds=120,
                )
                if writer_count % 20 == 0:
                    self.store.checkpoint_wal("PASSIVE")
                time.sleep(0.002)

        def reader_worker(reader_idx: int):
            ro_conn = create_readonly_connection(self.db_path, timeout=3.0)
            try:
                while not stop_event.is_set():
                    try:
                        cursor = execute_readonly_with_retry(
                            ro_conn,
                            "SELECT COUNT(*) AS total, AVG(rate_ths) AS avg_rate FROM telemetry_samples",
                            max_retries=3,
                            initial_backoff=0.005,
                        )
                        _ = cursor.fetchone()
                        reader_counts[reader_idx] += 1
                    except Exception as exc:
                        reader_errors.append(exc)
                    time.sleep(0.005)
            finally:
                ro_conn.close()

        # Seed initial data
        self.store.record_sample(
            observed_ts=time.time(),
            miner_key="seed|10.0.0.1:4028",
            miner_name="seed",
            host="10.0.0.1",
            state="OK",
            responded=True,
            rate_ths=90.0,
            threshold_ths=90.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=120,
        )

        w_thread = threading.Thread(target=writer_worker, daemon=True)
        r_threads = [
            threading.Thread(target=reader_worker, args=(i,), daemon=True)
            for i in range(4)
        ]

        w_thread.start()
        for t in r_threads:
            t.start()

        # Run concurrent load for 0.3s, then trigger TRUNCATE checkpoint mid-flight
        time.sleep(0.3)
        busy, log_frames, _ = self.store.checkpoint_wal("TRUNCATE")
        time.sleep(0.3)

        stop_event.set()
        w_thread.join(timeout=2.0)
        for t in r_threads:
            t.join(timeout=2.0)
        self.store.close()
        self.store = None

        self.assertEqual([], reader_errors, f"Reader errors occurred: {reader_errors}")
        self.assertGreater(writer_count, 10)
        for count in reader_counts:
            self.assertGreater(count, 5)


if __name__ == "__main__":
    unittest.main()
