"""Unit tests for Metrics Snapshot schema, validation, and atomicity (Spec 025)."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from app.metrics_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    VALID_ACQ_QUALITIES,
    VALID_COLLECTOR_STATUSES,
    VALID_MINER_STATES,
    VALID_TELEGRAM_OUTCOMES,
    MetricsSnapshot,
    load_metrics_snapshot,
    validate_snapshot_data,
    write_metrics_snapshot_atomic,
)


def _make_sample_payload(ts: float | None = None) -> dict:
    now = ts or time.time()
    return {
        "schema_version": 1,
        "generated_ts": now,
        "monitor": {
            "process_start_ts": now - 1000.0,
            "tick_sequence": 42,
            "last_tick_completed_ts": now - 2.0,
            "telegram_poller_ts": now - 5.0,
            "telegram_sender_ts": now - 3.0,
            "queue_depth": 1,
        },
        "miners": [
            {
                "miner_id": "S19JPRO-1",
                "sample_ts": now - 2.0,
                "responded": True,
                "rate_ths": 104.5,
                "threshold_ths": 90.0,
                "state": "OK",
                "active_boards": 3,
                "expected_boards": 3,
                "episode_active": False,
                "episode_duration_seconds": 0.0,
                "acquisition_quality": "valid",
                "acquisition_latency_seconds": 0.12,
            },
            {
                "miner_id": "S19JPRO-2",
                "sample_ts": now - 2.0,
                "responded": False,
                "rate_ths": None,
                "threshold_ths": 90.0,
                "state": "OFFLINE",
                "active_boards": None,
                "expected_boards": 3,
                "episode_active": True,
                "episode_duration_seconds": 120.5,
                "acquisition_quality": "timeout",
                "acquisition_latency_seconds": 5.0,
            },
        ],
        "telegram": {
            "enqueued_total": 10,
            "sent_total": 9,
            "send_error_total": 0,
            "dropped_total": 0,
            "bypass_total": 1,
            "fallback_total": 0,
        },
        "collector": {
            "status": "ok",
            "age_seconds": 45.0,
        },
        "acquisition": {
            "epoch_duration_seconds": 0.35,
        },
    }


class TestMetricsSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_valid_payload_parsing(self):
        payload = _make_sample_payload()
        is_val, parsed, reason = validate_snapshot_data(payload)
        self.assertTrue(is_val)
        self.assertEqual(reason, "ok")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.schema_version, 1)
        self.assertEqual(len(parsed.miners), 2)
        self.assertEqual(parsed.miners[0].rate_ths, 104.5)
        self.assertIsNone(parsed.miners[1].rate_ths)

    def test_reject_nan_infinity(self):
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            payload = _make_sample_payload()
            payload["miners"][0]["rate_ths"] = bad_val
            is_val, _, reason = validate_snapshot_data(payload)
            self.assertFalse(is_val)
            self.assertIn("invalid_rate", reason)

    def test_reject_ip_address_in_miner_id(self):
        payload = _make_sample_payload()
        payload["miners"][0]["miner_id"] = "192.168.1.101"
        is_val, _, reason = validate_snapshot_data(payload)
        self.assertFalse(is_val)
        self.assertIn("invalid_id", reason)

    def test_reject_duplicate_miner_id(self):
        payload = _make_sample_payload()
        payload["miners"][1]["miner_id"] = "S19JPRO-1"
        is_val, _, reason = validate_snapshot_data(payload)
        self.assertFalse(is_val)
        self.assertIn("invalid_id", reason)

    def test_reject_invalid_enums(self):
        # Invalid miner state
        p1 = _make_sample_payload()
        p1["miners"][0]["state"] = "SUPER_HOT"
        is_val, _, reason = validate_snapshot_data(p1)
        self.assertFalse(is_val)
        self.assertIn("invalid_state", reason)

        # Invalid collector status
        p2 = _make_sample_payload()
        p2["collector"]["status"] = "crashed"
        is_val, _, reason = validate_snapshot_data(p2)
        self.assertFalse(is_val)
        self.assertIn("collector_invalid_status", reason)

        # Invalid quality
        p3 = _make_sample_payload()
        p3["miners"][0]["acquisition_quality"] = "perfect"
        is_val, _, reason = validate_snapshot_data(p3)
        self.assertFalse(is_val)
        self.assertIn("invalid_quality", reason)

    def test_atomic_write_and_load(self):
        target_path = self.base_path / "diagnostics" / "metrics" / "current.json"
        payload = _make_sample_payload()

        success = write_metrics_snapshot_atomic(target_path, payload)
        self.assertTrue(success)
        self.assertTrue(target_path.exists())

        # Load fresh
        is_fresh, parsed, age, reason = load_metrics_snapshot(target_path, max_age_seconds=60.0)
        self.assertTrue(is_fresh)
        self.assertIsNotNone(parsed)
        self.assertEqual(reason, "ok")
        self.assertLessEqual(age, 2.0)

    def test_staleness_detection(self):
        target_path = self.base_path / "diagnostics" / "metrics" / "current.json"
        old_time = time.time() - 120.0  # 120s old
        payload = _make_sample_payload(ts=old_time)

        write_metrics_snapshot_atomic(target_path, payload)

        is_fresh, parsed, age, reason = load_metrics_snapshot(target_path, max_age_seconds=60.0)
        self.assertFalse(is_fresh)
        self.assertIsNotNone(parsed)  # Parsed is still available for diagnostic age
        self.assertGreaterEqual(age, 120.0)
        self.assertIn("snapshot_stale", reason)


if __name__ == "__main__":
    unittest.main()
