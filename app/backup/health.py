"""Small metadata reads only: no database, hashing, networking or worker threads."""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
ARGENTINA_TZ = dt.timezone(dt.timedelta(hours=-3))


def absolute_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class BackupSettings:
    enabled: bool
    root: Path
    staging_root: Path
    max_age_hours: float = 30
    max_run_seconds: float = 300
    minimum_free_bytes: int = 1073741824

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> BackupSettings:
        raw = config.get("backup", {})
        if not isinstance(raw, dict):
            raise ValueError("backup_not_object")
        root = absolute_path(raw.get("root") or config.get("backup_root") or "backups")
        age = float(raw.get("max_age_hours", 30))
        duration = float(raw.get("max_run_seconds", 300))
        free = int(raw.get("minimum_free_bytes", 1073741824))
        enabled = raw.get("enabled", bool(config.get("backup_root")))
        if not isinstance(enabled, bool) or not math.isfinite(age) or not 1 <= age <= 168:
            raise ValueError("invalid_backup_settings")
        if not math.isfinite(duration) or not 1 <= duration <= 300 or free < 0:
            raise ValueError("invalid_backup_limits")
        return cls(enabled, root, absolute_path(raw.get("staging_root") or root.with_name(root.name + "-staging")), age, duration, free)


def read_small_json(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("metadata_too_large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("metadata_not_object")
    return value


def inspect_backup(
    root: str | Path = "backups", *, now_ts: float | None = None,
    max_age_seconds: float = 108000, enabled: bool = True,
) -> dict[str, Any]:
    """Report the producer's verified snapshot metadata, not a fresh hash check."""
    if not enabled:
        return {"verified": False, "state": "disabled", "reason": "disabled"}
    current = time.time() if now_ts is None else now_ts
    root = absolute_path(root)
    result: dict[str, Any] = {"verified": False, "state": "missing", "reason": "no_backups"}
    if root.exists() and not (root / ".miner-alerts-backup-root-v1").is_file():
        return {"verified": False, "state": "failed", "reason": "missing_root_marker"}
    candidates = []
    try:
        verified = root / "verified"
        candidates = sorted((p for p in verified.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
        if candidates:
            folder = candidates[0]
            if folder.is_symlink() or folder.resolve().parent != verified.resolve():
                raise ValueError("backup_path_escape")
            manifest = read_small_json(folder / "manifest.json")
            database = folder / "miner_alerts.db"
            stat = database.stat()
            completed = dt.datetime.fromisoformat(manifest["completed_ts"].replace("Z", "+00:00"))
            if completed.tzinfo is None:
                raise ValueError("timestamp_without_timezone")
            stamp = completed.timestamp()
            if (manifest.get("manifest_version") != 1 or manifest.get("integrity_result") != "ok"
                    or manifest.get("backup_id") != folder.name or database.is_symlink()
                    or manifest.get("database_file") != "miner_alerts.db"
                    or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("sha256", "")))
                    or manifest.get("size_bytes") != stat.st_size or stat.st_size <= 0
                    or stat.st_mtime > stamp + 2 or stamp > current + 300):
                raise ValueError("invalid_backup_metadata")
            local = completed.astimezone(ARGENTINA_TZ)
            fresh = current - stamp <= max_age_seconds
            result = dict(verified=fresh, state="verified" if fresh else "stale",
                          reason="ok" if fresh else "backup_expired", backup_id=folder.name,
                          size_mb=stat.st_size / (1024 * 1024), time_str=local.strftime("%H:%M"),
                          date_str=local.strftime("%d/%m"), completed_ts=stamp,
                          age_hours=round(max(0, current - stamp) / 3600, 1))
    except FileNotFoundError:
        if candidates:
            result = dict(verified=False, state="failed", reason="incomplete_backup")
    except (OSError, ValueError, KeyError, TypeError):
        result = dict(verified=False, state="failed", reason="invalid_backup_metadata")
    try:
        job = read_small_json(root / "last_run.json")
        finished = float(job["finished_ts"])
        if not math.isfinite(finished) or finished > current + 300:
            raise ValueError("invalid_job_timestamp")
        if finished >= result.get("completed_ts", 0) and job.get("result") != "verified":
            if job.get("result") == "running" and current - finished <= 330:
                result = dict(result, verified=False, state="running", reason="backup_in_progress")
            else:
                result = dict(result, verified=False, state="failed", reason="last_job_failed")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError):
        result = dict(result, verified=False, state="failed", reason="invalid_job_metadata")
    return result
