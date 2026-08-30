"""Unit tests for EventStore Backup, Retention and Staging Restore (Spec 028).

Verifies:
- Online SQLite backup via 256-page chunks while source database is active.
- Manifest v1 generation with SHA-256, page metrics, schema version and allowlisted table counts.
- Full SQLite integrity check (PRAGMA integrity_check == 'ok').
- Safe root marker requirement (.miner-alerts-backup-root-v1).
- Disjoint non-overlapping path validation (root, staging, repo, source DB).
- Exclusive file lock preventing concurrent/overlapping runs.
- Free-space pre/post validation.
- Retention bucket calculation (14 daily, 8 weekly, 12 monthly UTC generations) with safe dry-run.
- Staging-only restore verification (checksum, integrity, schema, count comparisons).
- Failure closed on tampering, corrupt hashes, or invalid destinations.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.event_store_backup import (
    ROOT_MARKER_FILENAME,
    EventStoreBackup,
    RetentionPolicy,
    compute_file_sha256,
)


class TestEventStoreBackup(unittest.TestCase):
    """Tests for backup creation, manifests, locking, and path validation."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)

        # Source database in disjoint location
        self.source_dir = self.base_path / "repo" / "data"
        self.source_dir.mkdir(parents=True)
        self.source_db = self.source_dir / "miner_alerts.db"

        # Initialize test database with known tables
        conn = sqlite3.connect(str(self.source_db))
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA user_version = 6")
        cur.execute("CREATE TABLE telemetry_samples (id INTEGER PRIMARY KEY, miner_name TEXT, rate_ths REAL)")
        cur.execute("CREATE TABLE operational_events (id INTEGER PRIMARY KEY, event_type TEXT)")
        cur.execute("CREATE TABLE reboot_decisions (id INTEGER PRIMARY KEY, miner_name TEXT, result TEXT)")
        cur.execute("CREATE TABLE collector_runs (id INTEGER PRIMARY KEY, status TEXT)")
        for i in range(10):
            cur.execute("INSERT INTO telemetry_samples (miner_name, rate_ths) VALUES (?, ?)", (f"m{i}", 100.0 + i))
            cur.execute("INSERT INTO operational_events (event_type) VALUES (?)", (f"event_{i}",))
        conn.commit()
        conn.close()

        # Backup root in separate off-repo directory
        self.backup_root = self.base_path / "backups"
        self.backup_root.mkdir(parents=True)
        (self.backup_root / ROOT_MARKER_FILENAME).write_text("version=1\n", encoding="utf-8")

        # Staging root
        self.staging_root = self.base_path / "staging"
        self.staging_root.mkdir(parents=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_backup_creation_and_manifest(self):
        """Standard backup produces verified database and accurate manifest."""
        tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,  # low threshold for tests
        )

        run_result = tool.run_backup()
        self.assertEqual(run_result["result"], "verified")
        self.assertIsNotNone(run_result["backup_id"])

        backup_id = run_result["backup_id"]
        backup_dir = self.backup_root / "verified" / backup_id
        self.assertTrue(backup_dir.exists())

        backed_db = backup_dir / "miner_alerts.db"
        manifest_file = backup_dir / "manifest.json"
        self.assertTrue(backed_db.exists())
        self.assertTrue(manifest_file.exists())

        # Check manifest contents
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 1)
        self.assertEqual(manifest["method"], "sqlite_connection_backup")
        self.assertEqual(manifest["integrity_result"], "ok")
        self.assertEqual(manifest["source_schema_version"], 6)
        self.assertEqual(manifest["table_counts"]["telemetry_samples"], 10)
        self.assertEqual(manifest["table_counts"]["operational_events"], 10)
        self.assertEqual(manifest["table_counts"]["reboot_decisions"], 0)

        # Check SHA256 integrity
        actual_hash = compute_file_sha256(backed_db)
        self.assertEqual(manifest["sha256"], actual_hash)
        self.assertEqual(manifest["size_bytes"], backed_db.stat().st_size)

    def test_concurrent_writes_during_backup(self):
        """Backup completes cleanly even when concurrent writes happen on source DB."""
        import threading

        tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
            chunk_pages=2,
            sleep_seconds=0.05,
        )

        def writer():
            time.sleep(0.02)
            conn = sqlite3.connect(str(self.source_db), timeout=5.0)
            conn.execute("INSERT INTO operational_events (event_type) VALUES ('concurrent_event')")
            conn.commit()
            conn.close()

        t = threading.Thread(target=writer)
        t.start()
        run_result = tool.run_backup()
        t.join()
        self.assertEqual(run_result["result"], "verified")

        backup_id = run_result["backup_id"]
        backup_dir = self.backup_root / "verified" / backup_id
        backed_db = backup_dir / "miner_alerts.db"

        # Verify integrity of the backed up database
        conn = sqlite3.connect(str(backed_db))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        self.assertEqual(integrity, "ok")

    def test_missing_root_marker_fails_closed(self):
        """Missing root marker file aborts run with blocked_path."""
        (self.backup_root / ROOT_MARKER_FILENAME).unlink()

        tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
        )
        run_result = tool.run_backup()
        self.assertEqual(run_result["result"], "blocked_path")
        self.assertEqual(run_result["reason_code"], "missing_root_marker")

    def test_overlapping_paths_rejected(self):
        """Backup root or staging root inside repository or source DB path fails closed."""
        tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.source_dir),  # overlap with source!
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
        )
        run_result = tool.run_backup()
        self.assertEqual(run_result["result"], "blocked_path")
        self.assertEqual(run_result["reason_code"], "overlapping_paths")

    def test_exclusive_lock_prevents_overlap(self):
        """Second run exits with skipped_locked if .backup.lock is active."""
        tool1 = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
        )
        tool2 = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
        )

        with tool1._acquire_lock():
            run_result = tool2.run_backup()
            self.assertEqual(run_result["result"], "skipped_locked")
            self.assertEqual(run_result["reason_code"], "lock_active")

    @patch("shutil.disk_usage")
    def test_free_space_pre_check(self, mock_usage):
        """Fails closed with blocked_space if free disk space is under threshold."""
        mock_usage.return_value = shutil._ntuple_diskusage(1000000, 950000, 50000)  # 50 KB free

        tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=100000,  # 100 KB required > 50 KB free
        )
        run_result = tool.run_backup()
        self.assertEqual(run_result["result"], "blocked_space")
        self.assertEqual(run_result["reason_code"], "insufficient_free_space")


class TestEventStoreRetention(unittest.TestCase):
    """Tests for retention policy and safe dry-run deletion."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.backup_root = Path(self.tmp_dir.name) / "backups"
        self.backup_root.mkdir(parents=True)
        (self.backup_root / ROOT_MARKER_FILENAME).write_text("version=1\n", encoding="utf-8")
        self.verified_dir = self.backup_root / "verified"
        self.verified_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _create_mock_backup(self, backup_id: str, ts_iso: str):
        bdir = self.verified_dir / backup_id
        bdir.mkdir(parents=True)
        db_file = bdir / "miner_alerts.db"
        db_file.write_bytes(b"mock_db_content")
        manifest = {
            "manifest_version": 1,
            "backup_id": backup_id,
            "completed_ts": ts_iso,
            "sha256": compute_file_sha256(db_file),
            "integrity_result": "ok",
        }
        (bdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_retention_union_and_dry_run(self):
        """Retention preserves daily, weekly, monthly union and respects dry-run."""
        # Create 20 mock daily backups spanning 20 days
        for day in range(1, 21):
            bid = f"2026-08-{day:02d}T120000_abc{day:02d}"
            iso_ts = f"2026-08-{day:02d}T12:00:00Z"
            self._create_mock_backup(bid, iso_ts)

        policy = RetentionPolicy(daily=14, weekly=8, monthly=12)
        tool = EventStoreBackup(
            source_db_path="dummy.db",
            backup_root=str(self.backup_root),
            staging_root=str(Path(self.tmp_dir.name) / "staging"),
            retention_policy=policy,
        )

        # 1. Dry run
        dry_result = tool.apply_retention(dry_run=True)
        self.assertEqual(dry_result["status"], "dry_run")
        self.assertEqual(len(dry_result["kept"]), 15)  # 14 newest days + 1 distinct weekly generation
        self.assertEqual(len(dry_result["to_delete"]), 5)  # 5 unkept generations

        # In dry run, files must NOT be deleted
        self.assertEqual(len(list(self.verified_dir.iterdir())), 20)

        # 2. Apply deletion
        apply_result = tool.apply_retention(dry_run=False)
        self.assertEqual(apply_result["status"], "applied")
        self.assertEqual(len(apply_result["deleted"]), 5)
        self.assertEqual(len(list(self.verified_dir.iterdir())), 15)


class TestEventStoreStagedRestore(unittest.TestCase):
    """Tests for staging restore drills and checksum/schema validation."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)

        self.source_dir = self.base_path / "source"
        self.source_dir.mkdir(parents=True)
        self.source_db = self.source_dir / "miner_alerts.db"

        # Create source DB
        conn = sqlite3.connect(str(self.source_db))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA user_version = 6")
        conn.execute("CREATE TABLE telemetry_samples (id INTEGER PRIMARY KEY, miner_name TEXT)")
        conn.execute("INSERT INTO telemetry_samples (miner_name) VALUES ('m23')")
        conn.commit()
        conn.close()

        self.backup_root = self.base_path / "backups"
        self.backup_root.mkdir(parents=True)
        (self.backup_root / ROOT_MARKER_FILENAME).write_text("version=1\n", encoding="utf-8")

        self.staging_root = self.base_path / "staging"
        self.staging_root.mkdir(parents=True)

        self.tool = EventStoreBackup(
            source_db_path=str(self.source_db),
            backup_root=str(self.backup_root),
            staging_root=str(self.staging_root),
            minimum_free_bytes=1024,
        )
        self.backup_res = self.tool.run_backup()
        self.backup_id = self.backup_res["backup_id"]

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_staging_restore_success(self):
        """Restore drill validates integrity, checksum, schema and table counts."""
        target_dir = self.staging_root / "restore_drill_01"
        res = self.tool.restore_staging(backup_id=self.backup_id, target_dir=str(target_dir))

        self.assertEqual(res["result"], "passed")
        self.assertTrue(res["checksum_ok"])
        self.assertTrue(res["integrity_ok"])
        self.assertTrue(res["schema_ok"])
        self.assertTrue(res["counts_ok"])

        restored_db = target_dir / "miner_alerts.db"
        self.assertTrue(restored_db.exists())

        conn = sqlite3.connect(str(restored_db))
        count = conn.execute("SELECT COUNT(*) FROM telemetry_samples").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_restore_tampered_backup_fails(self):
        """Tampering with verified database causes checksum failure and aborts restore."""
        backup_db = self.backup_root / "verified" / self.backup_id / "miner_alerts.db"
        # Modify 1 byte in backup file
        with open(backup_db, "r+b") as f:
            f.seek(50)
            f.write(b"\xFF")

        target_dir = self.staging_root / "restore_drill_tampered"
        res = self.tool.restore_staging(backup_id=self.backup_id, target_dir=str(target_dir))

        self.assertEqual(res["result"], "failed")
        self.assertFalse(res["checksum_ok"])
        self.assertEqual(res["reason_code"], "checksum_mismatch")
        self.assertFalse((target_dir / "miner_alerts.db").exists())

    def test_restore_over_live_db_forbidden(self):
        """Targeting live source database path is strictly forbidden."""
        res = self.tool.restore_staging(backup_id=self.backup_id, target_dir=str(self.source_dir))
        self.assertEqual(res["result"], "failed")
        self.assertEqual(res["reason_code"], "target_equals_source_or_repo")


if __name__ == "__main__":
    unittest.main()
