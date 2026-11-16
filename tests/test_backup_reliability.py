"""Spec 094: real SQLite copies, bounded metadata and job failure contracts."""

import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest

from app.backup.health import BackupSettings, inspect_backup
from app.telegram.daily_digest import fetch_daily_digest_metrics, format_daily_digest
from tools.event_store_backup import EventStoreBackup, ROOT_MARKER_FILENAME
from tools.run_event_store_backup import publish_result, run_job


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "source # encoded" / "db.sqlite"
    source.parent.mkdir()
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA user_version=7")
        connection.execute("CREATE TABLE telemetry_samples(id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO telemetry_samples VALUES(1)")
    root = tmp_path / "backups"
    root.mkdir()
    (root / ROOT_MARKER_FILENAME).write_text("version=1\n")
    staging = tmp_path / "staging"
    tool = EventStoreBackup(str(source), str(root), str(staging), minimum_free_bytes=0)
    return source, root, staging, tool


def test_default_staging_is_disjoint_and_source_uri_escaped(setup):
    source, root, _, _ = setup
    tool = EventStoreBackup(str(source), str(root), minimum_free_bytes=0)
    assert tool.staging_root.parent == root.parent and tool.staging_root != root
    assert tool.run_backup()["result"] == "verified"


def test_real_producer_manifest_and_freshness(setup):
    _, root, _, tool = setup
    result = tool.run_backup()
    assert result["result"] == "verified"
    health = inspect_backup(root)
    assert health["verified"] and health["state"] == "verified"
    stale = inspect_backup(root, now_ts=health["completed_ts"] + 108001)
    assert not stale["verified"] and stale["state"] == "stale"
    assert inspect_backup(root, enabled=False)["state"] == "disabled"


@pytest.mark.parametrize("corruption", ["missing_manifest", "invalid_json", "bad_integrity", "wrong_id", "size", "future", "huge_manifest", "changed_db"])
def test_metadata_failures_never_show_ok(setup, corruption):
    _, root, _, tool = setup
    result = tool.run_backup()
    folder = root / "verified" / result["backup_id"]
    path = folder / "manifest.json"
    manifest = json.loads(path.read_text())
    if corruption == "missing_manifest":
        path.unlink()
    elif corruption == "invalid_json":
        path.write_text("{")
    elif corruption == "huge_manifest":
        path.write_text(" " * 65537)
    elif corruption == "size":
        with (folder / "miner_alerts.db").open("ab") as stream:
            stream.write(b"changed")
    elif corruption == "changed_db":
        future = dt.datetime.now(dt.timezone.utc).timestamp() + 10
        os.utime(folder / "miner_alerts.db", (future, future))
    else:
        manifest.update({"bad_integrity": {"integrity_result": "bad"},
                         "wrong_id": {"backup_id": "wrong"},
                         "future": {"completed_ts": "2099-01-01T00:00:00+00:00"}}[corruption])
        path.write_text(json.dumps(manifest))
    health = inspect_backup(root)
    assert not health["verified"] and health["state"] == "failed"


def test_last_job_failure_overrides_old_healthy_copy(setup):
    _, root, _, tool = setup
    tool.run_backup()
    publish_result(root, {"result": "failed", "finished_ts": dt.datetime.now(dt.timezone.utc).timestamp()})
    assert inspect_backup(root)["reason"] == "last_job_failed"
    (root / "last_run.json").write_text("bad")
    assert inspect_backup(root)["reason"] == "invalid_job_metadata"


def test_partial_failure_and_timeout_release_lock_without_promotion(setup):
    _, root, _, tool = setup
    result = tool.run_backup(step_callback=Mock(side_effect=TimeoutError("test")))
    assert result["result"] == "failed"
    assert not (root / ".backup.lock").exists()
    assert not (root / "verified").exists()
    assert tool.run_backup()["result"] == "verified"


def test_corrupt_source_fails_without_promotion(setup):
    source, root, _, tool = setup
    source.write_bytes(b"not SQLite")
    assert tool.run_backup()["result"] == "failed"
    assert not (root / ".backup.lock").exists()
    assert not (root / "verified").exists()


@pytest.mark.parametrize("target", ["../outside", "../source # encoded/nested", "."])
def test_restore_cannot_escape_staging(setup, target):
    source, _, staging, tool = setup
    original = source.read_bytes()
    result = tool.run_backup()
    restored = tool.restore_staging(result["backup_id"], str(staging / target))
    assert restored["result"] == "failed"
    assert source.read_bytes() == original


@pytest.mark.parametrize("backup_id", ["..", "../x", "..\\x", "C:other"])
def test_restore_rejects_backup_id_traversal(setup, backup_id):
    _, _, staging, tool = setup
    assert tool.restore_staging(backup_id, str(staging / "drill"))["reason_code"] == "invalid_backup_id"


def test_restore_checks_checksum_integrity_schema_and_counts(setup):
    _, _, staging, tool = setup
    result = tool.run_backup()
    restored = tool.restore_staging(result["backup_id"], str(staging / "drill"))
    assert restored["result"] == "passed"
    assert all(restored[k] for k in ("checksum_ok", "integrity_ok", "schema_ok", "counts_ok"))


def test_job_publishes_result_and_preserves_existing_source(setup, tmp_path):
    source, root, staging, _ = setup
    config = tmp_path / "config.json"
    data = {"event_store_path": str(source), "backup": {"enabled": True, "root": str(root),
            "staging_root": str(staging), "minimum_free_bytes": 0}}
    config.write_text(json.dumps(data))
    original = source.read_bytes()
    code, result = run_job(config)
    assert code == 0 and result["result"] == "verified"
    assert json.loads((root / "last_run.json").read_text())["result"] == "verified"
    assert source.read_bytes() == original
    assert not list(root.glob(".last_run.*.tmp"))
    data["backup"]["enabled"] = False
    config.write_text(json.dumps(data))
    assert run_job(config) == (0, {"result": "disabled"})


@pytest.mark.parametrize("raw", ["{", "[]", '{"backup": []}', '{"backup": {"max_age_hours": -1}}'])
def test_job_config_errors_are_explicit_and_sanitized(tmp_path, raw):
    config = tmp_path / "config.json"
    config.write_text(raw)
    assert run_job(config) == (1, {"result": "failed", "reason_code": "invalid_config"})


def test_nested_settings_override_flat_legacy_and_digest_disabled(tmp_path):
    settings = BackupSettings.from_config({"backup_root": str(tmp_path / "old"),
                                          "backup": {"enabled": False, "root": str(tmp_path / "new")}})
    assert settings.root == tmp_path / "new" and not settings.enabled
    metrics = fetch_daily_digest_metrics(tmp_path / "missing.db", [], backup_config={"backup": {"enabled": False}})
    assert metrics["backup_status"]["state"] == "disabled"
    assert "Deshabilitado" in format_daily_digest(metrics)


def test_scheduler_plan_is_hidden_bounded_and_uses_exact_venv():
    text = Path("tools/install_backup_task.ps1").read_text()
    assert '"tools\\run_event_store_backup.py"' in text
    assert '-StartWhenAvailable -Hidden' in text
    assert '-MultipleInstances IgnoreNew' in text
    assert '-Minutes 5' in text and '--config' in text
    assert 'Falling back' not in text


def test_running_job_is_distinct_from_failed_stuck_job(setup):
    _, root, _, _ = setup
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    publish_result(root, {"result": "running", "finished_ts": now})
    assert inspect_backup(root, now_ts=now + 10)["state"] == "running"
    assert inspect_backup(root, now_ts=now + 331)["state"] == "failed"


def test_removed_marker_never_reports_old_copy_as_healthy(setup):
    _, root, _, tool = setup
    assert tool.run_backup()["result"] == "verified"
    (root / ROOT_MARKER_FILENAME).unlink()
    assert inspect_backup(root)["reason"] == "missing_root_marker"
