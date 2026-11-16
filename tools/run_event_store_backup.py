"""Bounded scheduled job with an atomic, secret-free result file."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backup.health import BackupSettings, absolute_path
from tools.event_store_backup import EventStoreBackup


def publish_result(root: Path, result: dict[str, Any]) -> None:
    target = root / "last_run.json"
    temporary = root / f".last_run.{os.getpid()}.tmp"
    try:
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def run_job(config_path: Path) -> tuple[int, dict[str, Any]]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict):
            raise ValueError("config_not_object")
        settings = BackupSettings.from_config(config)
    except (OSError, ValueError, TypeError):
        return 1, {"result": "failed", "reason_code": "invalid_config"}
    if not settings.enabled:
        return 0, {"result": "disabled"}
    source = absolute_path(config.get("event_store_path") or config.get("db_path") or "data/miner_alerts.db")
    tool = EventStoreBackup(str(source), str(settings.root), str(settings.staging_root),
                            minimum_free_bytes=settings.minimum_free_bytes,
                            max_run_seconds=min(settings.max_run_seconds, 240))
    valid, reason = tool._validate_paths()
    if not valid:
        return 1, {"result": "blocked_path", "reason_code": reason}
    started = time.time()
    try:
        publish_result(settings.root, {"result": "running", "started_ts": started, "finished_ts": started})
        result = tool.run_backup()
    except Exception as exc:
        result = {"result": "failed", "reason_code": type(exc).__name__}
    result.update(started_ts=started, finished_ts=time.time())
    try:
        publish_result(settings.root, result)
    except OSError:
        return 1, {"result": "failed", "reason_code": "result_publish_failed"}
    return (0 if result.get("result") == "verified" else 1), result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        try:
            config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
            settings = BackupSettings.from_config(config)
            tool = EventStoreBackup(str(absolute_path(config.get("event_store_path") or config.get("db_path") or "data/miner_alerts.db")), str(settings.root), str(settings.staging_root))
            valid, reason = tool._validate_paths()
            if not settings.enabled or not valid or not tool.source_db_path.is_file():
                print(json.dumps({"valid": False, "reason": reason if settings.enabled else "disabled"}))
                return 1
            print(json.dumps({"valid": True, "root": str(settings.root), "staging_root": str(settings.staging_root), "max_run_seconds": settings.max_run_seconds}))
            return 0
        except (OSError, ValueError, TypeError, AttributeError):
            print(json.dumps({"valid": False, "reason": "invalid_config"}))
            return 1
    code, result = run_job(Path(args.config).resolve())
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
