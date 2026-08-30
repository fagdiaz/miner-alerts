"""Unit tests for Prometheus Metrics Exporter (Spec 025)."""

import tempfile
import time
import unittest
from pathlib import Path

from app.metrics_snapshot import write_metrics_snapshot_atomic
from tests.test_metrics_snapshot import _make_sample_payload
from tools.metrics_exporter import METRIC_FAMILIES_DEF, render_prometheus_text


class TestMetricsExporter(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)
        self.snapshot_path = self.base_path / "current.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_missing_snapshot_exports_health_only(self):
        """Missing snapshot produces valid=0 and duration only."""
        text, count = render_prometheus_text(self.snapshot_path)
        self.assertIn("miner_alerts_snapshot_valid 0", text)
        self.assertNotIn("miner_alerts_monitor_up", text)
        self.assertNotIn("miner_alerts_miner_state", text)
        self.assertLessEqual(count, 3)

    def test_stale_snapshot_exports_health_only(self):
        """Snapshot older than 60 seconds produces valid=0, age, and duration only."""
        old_time = time.time() - 150.0
        payload = _make_sample_payload(ts=old_time)
        write_metrics_snapshot_atomic(self.snapshot_path, payload)

        text, count = render_prometheus_text(self.snapshot_path, stale_seconds=60.0)
        self.assertIn("miner_alerts_snapshot_valid 0", text)
        self.assertIn("miner_alerts_snapshot_age_seconds", text)
        self.assertNotIn("miner_alerts_monitor_up", text)
        self.assertNotIn("miner_alerts_miner_rate_ths", text)
        self.assertLessEqual(count, 3)

    def test_fresh_snapshot_exposition_and_cardinality(self):
        """Fresh snapshot exports all families with bounded cardinality."""
        now = time.time()
        # 4 miners payload
        payload = _make_sample_payload(ts=now)
        # Add 2 more miners to have 4 miners (production fleet size)
        for i in (3, 4):
            payload["miners"].append(
                {
                    "miner_id": f"S19JPRO-{i}",
                    "sample_ts": now - 1.0,
                    "responded": True,
                    "rate_ths": 100.0,
                    "threshold_ths": 90.0,
                    "state": "OK",
                    "active_boards": 3,
                    "expected_boards": 3,
                    "episode_active": False,
                    "episode_duration_seconds": 0.0,
                    "acquisition_quality": "valid",
                    "acquisition_latency_seconds": 0.1,
                }
            )

        write_metrics_snapshot_atomic(self.snapshot_path, payload)

        start_scrape = time.perf_counter()
        text, count = render_prometheus_text(self.snapshot_path, stale_seconds=60.0, now=now)
        scrape_ms = (time.perf_counter() - start_scrape) * 1000.0

        # Performance goal: scrape under 250 ms
        self.assertLess(scrape_ms, 250.0)

        # Verify families are present
        self.assertIn("miner_alerts_snapshot_valid 1", text)
        self.assertIn("miner_alerts_monitor_up 1", text)
        self.assertIn("miner_alerts_telegram_messages_total", text)
        self.assertIn('miner="S19JPRO-1"', text)
        self.assertIn('miner="S19JPRO-4"', text)

        # When miner 2 is OFFLINE with null rate and active_boards, those 2 series are omitted
        self.assertEqual(count, 101)
        self.assertLessEqual(count, 128)

        # When all 4 miners report active rates and boards, cardinality reaches the exact ceiling of 103
        payload["miners"][1]["rate_ths"] = 0.0
        payload["miners"][1]["active_boards"] = 0
        write_metrics_snapshot_atomic(self.snapshot_path, payload)
        text_full, count_full = render_prometheus_text(self.snapshot_path, stale_seconds=60.0, now=now)
        self.assertEqual(count_full, 103)
        self.assertLessEqual(count_full, 128)

    def test_all_26_families_defined(self):
        """Verifies exactly 26 metric families are registered."""
        self.assertEqual(len(METRIC_FAMILIES_DEF), 26)


class TestObservabilityCompose(unittest.TestCase):
    """Static tests for docker-compose.observability.yml and provisioning files (T004)."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.compose_file = self.project_root / "docker-compose.observability.yml"

    def test_compose_pinned_images_and_security_topology(self):
        self.assertTrue(self.compose_file.exists())
        content = self.compose_file.read_text(encoding="utf-8")

        # Pinned images
        self.assertIn("prom/prometheus:v2.53.2", content)
        self.assertIn("grafana/grafana:11.1.0", content)

        # Loopback-only port bindings
        self.assertIn('"127.0.0.1:9090:9090"', content)
        self.assertIn('"127.0.0.1:3000:3000"', content)

        # No published host ports for exporter
        self.assertNotIn("9100:9100", content)

        # Prohibited mounts in volume declarations
        volume_lines = [line.strip() for line in content.splitlines() if line.strip().startswith("- ./") or line.strip().startswith("- /")]
        for vline in volume_lines:
            for prohibited in ("config.json", "state.json", ".db", "logs", ".git", "docker.sock"):
                self.assertNotIn(prohibited, vline)

    def test_grafana_dashboards_valid_json(self):
        import json
        dash_dir = self.project_root / "observability" / "grafana" / "dashboards"
        self.assertTrue(dash_dir.exists())
        for dash_file in dash_dir.glob("*.json"):
            data = json.loads(dash_file.read_text(encoding="utf-8"))
            self.assertIn("title", data)
            self.assertIn("panels", data)
            self.assertGreater(len(data["panels"]), 0)


if __name__ == "__main__":
    unittest.main()

