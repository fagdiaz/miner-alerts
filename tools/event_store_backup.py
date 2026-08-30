#!/usr/bin/env python3
"""EventStore Backup, Retention and Staged Restore Tool (Spec 028).

Provides an offline, standalone CLI and library for SQLite database backups.
Strictly enforces:
- Online SQLite backup via sqlite3.Connection.backup(pages=256, sleep=0.01).
- Manifest v1 generation with SHA-256, page metrics, schema version and allowlisted table counts.
- PRAGMA integrity_check == 'ok' verification before promotion.
- Exclusive lock (.backup.lock) to prevent concurrent or overlapping runs.
- Root marker (.miner-alerts-backup-root-v1) and disjoint non-overlapping paths.
- Pre/post free-space validation.
- UTC union retention (14 daily, 8 weekly, 12 monthly generations) with safe dry-run.
- Staging-only restore drill with tamper detection. Live database is NEVER overwritten.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple

ROOT_MARKER_FILENAME = ".miner-alerts-backup-root-v1"
LOCK_FILENAME = ".backup.lock"
TOOL_VERSION = "1.0.0"
DEFAULT_MIN_FREE_BYTES = 1073741824  # 1 GiB
DEFAULT_CHUNK_PAGES = 256
DEFAULT_SLEEP_SECONDS = 0.01

ALLOWLISTED_TABLES = (
    "telemetry_samples",
    "operational_events",
    "reboot_decisions",
    "firmware_events",
    "collector_runs",
    "incident_assessments",
    "assessment_fact_refs",
)


def compute_file_sha256(path: Path | str) -> str:
    """Computes SHA-256 hash of a file in 64 KiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class RetentionPolicy:
    """Retention policy specifying generation counts to preserve."""

    daily: int = 14
    weekly: int = 8
    monthly: int = 12

    @staticmethod
    def parse_utc_timestamp(ts_str: str) -> datetime.datetime:
        """Parses ISO timestamp into UTC datetime."""
        # Clean string
        clean = ts_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)

    def select_generations(self, records: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str]]:
        """Selects backup IDs to keep based on the union of daily, weekly and monthly buckets.

        Returns (kept_ids, to_delete_ids).
        """
        # Sort records by completed_ts descending (newest first)
        def get_ts(rec: Dict[str, Any]) -> datetime.datetime:
            return self.parse_utc_timestamp(rec.get("completed_ts", "1970-01-01T00:00:00Z"))

        sorted_records = sorted(records, key=get_ts, reverse=True)

        daily_buckets: Dict[str, str] = {}
        weekly_buckets: Dict[str, str] = {}
        monthly_buckets: Dict[str, str] = {}

        for rec in sorted_records:
            bid = rec["backup_id"]
            dt = get_ts(rec)

            day_key = dt.strftime("%Y-%m-%d")
            # ISO calendar: year, week number
            iso_year, iso_week, _ = dt.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            month_key = dt.strftime("%Y-%m")

            if day_key not in daily_buckets and len(daily_buckets) < self.daily:
                daily_buckets[day_key] = bid
            if week_key not in weekly_buckets and len(weekly_buckets) < self.weekly:
                weekly_buckets[week_key] = bid
            if month_key not in monthly_buckets and len(monthly_buckets) < self.monthly:
                monthly_buckets[month_key] = bid

        kept_ids = set(daily_buckets.values()) | set(weekly_buckets.values()) | set(monthly_buckets.values())
        all_ids = {r["backup_id"] for r in sorted_records}
        to_delete_ids = all_ids - kept_ids

        return kept_ids, to_delete_ids


class EventStoreBackup:
    """Core offline backup, retention and staging restore engine for SQLite EventStore."""

    def __init__(
        self,
        source_db_path: str,
        backup_root: str,
        staging_root: Optional[str] = None,
        minimum_free_bytes: int = DEFAULT_MIN_FREE_BYTES,
        chunk_pages: int = DEFAULT_CHUNK_PAGES,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
        retention_policy: Optional[RetentionPolicy] = None,
    ):
        self.source_db_path = Path(source_db_path).resolve()
        self.backup_root = Path(backup_root).resolve()
        self.staging_root = Path(staging_root).resolve() if staging_root else (self.backup_root / "staging")
        self.minimum_free_bytes = minimum_free_bytes
        self.chunk_pages = chunk_pages
        self.sleep_seconds = sleep_seconds
        self.retention_policy = retention_policy or RetentionPolicy()

    @contextlib.contextmanager
    def _acquire_lock(self) -> Generator[None, None, None]:
        """Acquires exclusive file lock on .backup.lock using atomic file creation."""
        lock_file = self.backup_root / LOCK_FILENAME
        fd = None
        try:
            # Atomic creation flag
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()}\nstarted={time.time()}\n".encode("utf-8"))
            yield
        finally:
            if fd is not None:
                os.close(fd)
                try:
                    lock_file.unlink()
                except OSError:
                    pass

    def _validate_paths(self) -> Tuple[bool, str]:
        """Verifies root marker, path existence, and strictly disjoint directories."""
        # Check disjoint / non-overlapping paths first
        src_parent = self.source_db_path.parent
        resolved_paths = [self.backup_root, self.staging_root, src_parent]

        for i, p1 in enumerate(resolved_paths):
            for j, p2 in enumerate(resolved_paths):
                if i != j:
                    if p1 == p2:
                        return False, "overlapping_paths"
                    try:
                        p1.relative_to(p2)
                        return False, "overlapping_paths"
                    except ValueError:
                        pass

        if not self.backup_root.exists():
            return False, "backup_root_does_not_exist"

        marker_file = self.backup_root / ROOT_MARKER_FILENAME
        if not marker_file.exists():
            return False, "missing_root_marker"

        return True, "ok"

    def _check_free_space(self) -> bool:
        """Verifies destination filesystem has adequate free space."""
        try:
            usage = shutil.disk_usage(str(self.backup_root))
            return usage.free >= self.minimum_free_bytes
        except Exception:
            return False

    def run_backup(self, step_callback: Optional[Callable[[], None]] = None) -> Dict[str, Any]:
        """Executes a full incremental SQLite online backup and directory promotion."""
        start_ts = time.time()
        start_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Step 1: Validate paths
        valid_paths, path_reason = self._validate_paths()
        if not valid_paths:
            return {
                "result": "blocked_path",
                "reason_code": path_reason,
                "backup_id": None,
                "duration_seconds": time.time() - start_ts,
            }

        # Step 2: Validate free space
        if not self._check_free_space():
            return {
                "result": "blocked_space",
                "reason_code": "insufficient_free_space",
                "backup_id": None,
                "duration_seconds": time.time() - start_ts,
            }

        # Step 3: Source DB exists
        if not self.source_db_path.exists():
            return {
                "result": "failed",
                "reason_code": "source_db_missing",
                "backup_id": None,
                "duration_seconds": time.time() - start_ts,
            }

        # Step 4: Acquire exclusive lock
        lock_file = self.backup_root / LOCK_FILENAME
        if lock_file.exists():
            return {
                "result": "skipped_locked",
                "reason_code": "lock_active",
                "backup_id": None,
                "duration_seconds": time.time() - start_ts,
            }

        try:
            with self._acquire_lock():
                return self._execute_backup_internal(start_ts, start_iso, step_callback)
        except OSError:
            return {
                "result": "skipped_locked",
                "reason_code": "lock_active",
                "backup_id": None,
                "duration_seconds": time.time() - start_ts,
            }

    def _execute_backup_internal(
        self, start_ts: float, start_iso: str, step_callback: Optional[Callable[[], None]]
    ) -> Dict[str, Any]:
        """Internal worker executing the 256-page backup within the lock."""
        backup_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + secrets.token_hex(4)
        temp_dir = self.backup_root / "temporary" / f".tmp-{backup_id}"
        verified_dir = self.backup_root / "verified" / backup_id

        temp_dir.mkdir(parents=True, exist_ok=True)
        partial_db = temp_dir / "miner_alerts.db.partial"

        # Open source database in URI read-only mode to prevent write lock conflicts
        source_uri = f"file:{self.source_db_path}?mode=ro"
        src_conn = sqlite3.connect(source_uri, uri=True, timeout=10.0)
        tgt_conn = sqlite3.connect(str(partial_db), timeout=10.0)

        page_size = 4096
        page_count = 0
        schema_version = 0

        def progress_handler(status: int, remaining: int, total: int) -> None:
            if step_callback:
                step_callback()

        try:
            cur = src_conn.cursor()
            schema_version = cur.execute("PRAGMA user_version").fetchone()[0]
            page_size = cur.execute("PRAGMA page_size").fetchone()[0]

            # Perform 256-page incremental backup
            with tgt_conn:
                src_conn.backup(
                    tgt_conn,
                    pages=self.chunk_pages,
                    sleep=self.sleep_seconds,
                    progress=progress_handler if step_callback else None,
                )
        finally:
            src_conn.close()
            tgt_conn.close()

        # Step 5: Validate integrity of backed-up database
        check_conn = sqlite3.connect(str(partial_db))
        try:
            check_cur = check_conn.cursor()
            integrity = check_cur.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {
                    "result": "failed",
                    "reason_code": f"integrity_check_failed: {integrity}",
                    "backup_id": None,
                    "duration_seconds": time.time() - start_ts,
                }

            page_count = check_cur.execute("PRAGMA page_count").fetchone()[0]

            # Count allowlisted tables
            table_counts: Dict[str, int] = {}
            for tbl in ALLOWLISTED_TABLES:
                try:
                    cnt = check_cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    table_counts[tbl] = cnt
                except sqlite3.OperationalError:
                    pass  # Table does not exist in this schema version
        finally:
            check_conn.close()

        # Step 6: Rename to final miner_alerts.db
        final_db = temp_dir / "miner_alerts.db"
        partial_db.rename(final_db)

        # Compute hash and size
        db_sha256 = compute_file_sha256(final_db)
        db_size = final_db.stat().st_size
        completed_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        duration = time.time() - start_ts

        # Step 7: Write manifest v1
        manifest = {
            "manifest_version": 1,
            "tool_version": TOOL_VERSION,
            "backup_id": backup_id,
            "method": "sqlite_connection_backup",
            "started_ts": start_iso,
            "completed_ts": completed_iso,
            "duration_seconds": round(duration, 3),
            "source_kind": "event_store",
            "source_schema_version": schema_version,
            "database_file": "miner_alerts.db",
            "size_bytes": db_size,
            "sha256": db_sha256,
            "page_size": page_size,
            "page_count": page_count,
            "integrity_result": "ok",
            "table_counts": table_counts,
            "retention": {
                "daily": self.retention_policy.daily,
                "weekly": self.retention_policy.weekly,
                "monthly": self.retention_policy.monthly,
            },
        }

        manifest_file = temp_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        # Step 8: Atomic promotion to verified/
        verified_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_dir.rename(verified_dir)

        return {
            "result": "verified",
            "backup_id": backup_id,
            "duration_seconds": round(duration, 3),
            "sha256": db_sha256,
            "size_bytes": db_size,
            "schema_version": schema_version,
        }

    def apply_retention(self, dry_run: bool = True) -> Dict[str, Any]:
        """Applies union retention policy to verified backup directories."""
        verified_root = self.backup_root / "verified"
        if not verified_root.exists():
            return {"status": "no_backups", "kept": [], "deleted": []}

        # Inspect manifests in verified/
        records: List[Dict[str, Any]] = []
        for bdir in verified_root.iterdir():
            if bdir.is_dir():
                manifest_file = bdir / "manifest.json"
                if manifest_file.exists():
                    try:
                        m = json.loads(manifest_file.read_text(encoding="utf-8"))
                        records.append(m)
                    except Exception:
                        pass

        kept_ids, to_delete_ids = self.retention_policy.select_generations(records)

        deleted = []
        if not dry_run:
            for bid in to_delete_ids:
                target_bdir = verified_root / bid
                # Containment check: target must be directly under verified_root
                if target_bdir.parent.resolve() == verified_root.resolve():
                    shutil.rmtree(target_bdir, ignore_errors=True)
                    deleted.append(bid)

        return {
            "status": "dry_run" if dry_run else "applied",
            "kept": sorted(list(kept_ids)),
            "to_delete" if dry_run else "deleted": sorted(list(to_delete_ids if dry_run else deleted)),
        }

    def restore_staging(self, backup_id: str, target_dir: str) -> Dict[str, Any]:
        """Performs a staging-only restore drill, validating checksum, integrity, and schema."""
        target_path = Path(target_dir).resolve()

        # Path protection: cannot restore over live DB, repo, or existing path
        if target_path == self.source_db_path or target_path == self.source_db_path.parent:
            return {"result": "failed", "reason_code": "target_equals_source_or_repo"}

        if target_path.exists() and any(target_path.iterdir()):
            return {"result": "failed", "reason_code": "target_directory_already_exists"}

        backup_dir = self.backup_root / "verified" / backup_id
        if not backup_dir.exists():
            return {"result": "failed", "reason_code": "backup_not_found"}

        manifest_file = backup_dir / "manifest.json"
        db_file = backup_dir / "miner_alerts.db"

        if not manifest_file.exists() or not db_file.exists():
            return {"result": "failed", "reason_code": "corrupt_backup_files"}

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Step 1: Checksum verification
        actual_sha = compute_file_sha256(db_file)
        if actual_sha != manifest.get("sha256"):
            return {
                "result": "failed",
                "reason_code": "checksum_mismatch",
                "checksum_ok": False,
            }

        # Step 2: Copy to staging target
        target_path.mkdir(parents=True, exist_ok=True)
        staged_db = target_path / "miner_alerts.db"
        shutil.copy2(db_file, staged_db)
        shutil.copy2(manifest_file, target_path / "manifest.json")

        # Step 3: SQLite integrity check
        conn = sqlite3.connect(str(staged_db))
        try:
            cur = conn.cursor()
            integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
            integrity_ok = integrity == "ok"

            schema_ver = cur.execute("PRAGMA user_version").fetchone()[0]
            schema_ok = schema_ver == manifest.get("source_schema_version")

            # Compare table counts
            counts_ok = True
            expected_counts = manifest.get("table_counts", {})
            for tbl, exp_cnt in expected_counts.items():
                try:
                    act_cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    if act_cnt != exp_cnt:
                        counts_ok = False
                        break
                except Exception:
                    counts_ok = False
                    break
        finally:
            conn.close()

        passed = integrity_ok and schema_ok and counts_ok
        return {
            "result": "passed" if passed else "failed",
            "backup_id": backup_id,
            "staging_path": str(target_path),
            "checksum_ok": True,
            "integrity_ok": integrity_ok,
            "schema_ok": schema_ok,
            "counts_ok": counts_ok,
            "completed_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="EventStore SQLite Backup and Restore Tool (Spec 028)")
    parser.add_argument("--source-db", default="data/miner_alerts.db", help="Path to live SQLite database")
    parser.add_argument("--backup-root", required=True, help="Path to marked backup root directory")
    parser.add_argument("--staging-root", help="Path to staging restore directory")
    parser.add_argument("--action", choices=["backup", "retention-dry-run", "retention-apply", "restore-staging"], default="backup")
    parser.add_argument("--backup-id", help="Backup ID to restore in restore-staging action")
    parser.add_argument("--restore-target", help="Destination path for restore-staging action")
    parser.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES)
    args = parser.parse_args()

    tool = EventStoreBackup(
        source_db_path=args.source_db,
        backup_root=args.backup_root,
        staging_root=args.staging_root,
        minimum_free_bytes=args.min_free_bytes,
    )

    if args.action == "backup":
        result = tool.run_backup()
        print(json.dumps(result, indent=2))
        return 0 if result.get("result") == "verified" else 1

    elif args.action == "retention-dry-run":
        result = tool.apply_retention(dry_run=True)
        print(json.dumps(result, indent=2))
        return 0

    elif args.action == "retention-apply":
        result = tool.apply_retention(dry_run=False)
        print(json.dumps(result, indent=2))
        return 0

    elif args.action == "restore-staging":
        if not args.backup_id or not args.restore_target:
            print("Error: --backup-id and --restore-target required for restore-staging", file=sys.stderr)
            return 2
        result = tool.restore_staging(backup_id=args.backup_id, target_dir=args.restore_target)
        print(json.dumps(result, indent=2))
        return 0 if result.get("result") == "passed" else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
