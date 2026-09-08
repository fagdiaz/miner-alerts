"""Unit tests for Telegram visual charts engine (Spec 032)."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from app.event_store import EventStore
from app.telegram_charts import (
    fetch_miner_chart_data,
    fetch_fleet_chart_data,
    render_miner_chart_png,
    render_fleet_chart_png,
)

PNG_MAGIC_HEADER = b"\x89PNG\r\n\x1a\n"


class TestTelegramCharts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_alerts.db"
        self.store = EventStore(self.db_path)
        self.now = time.time()
        self._populate_fixtures()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def _populate_fixtures(self):
        # Insert 12 samples over 1 hour for miner 23 and miner 24
        for i in range(12):
            ts = self.now - (12 - i) * 300.0  # every 5 minutes
            # Miner 23: ~98 TH/s, 75°C, 5800 RPM
            self.store.record_sample(
                observed_ts=ts,
                miner_key="S19JPRO-23|192.168.100.23:4028",
                miner_name="S19JPRO-23",
                host="192.168.100.23",
                state="OK",
                responded=True,
                rate_ths=98.0 + (i % 3),
                threshold_ths=60.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=1000 + i * 300,
                telemetry={
                    "max_temp_c": 72.0 + (i % 4),
                    "fan_rpm_max": 5800 + i * 20,
                },
            )
            # Miner 24: ~94 TH/s, 70°C, 5600 RPM
            self.store.record_sample(
                observed_ts=ts,
                miner_key="S19JPRO-24|192.168.100.24:4028",
                miner_name="S19JPRO-24",
                host="192.168.100.24",
                state="OK",
                responded=True,
                rate_ths=94.0 + (i % 2),
                threshold_ths=60.0,
                active_boards=3,
                expected_boards=3,
                elapsed_seconds=1000 + i * 300,
                telemetry={
                    "max_temp_c": 70.0 + (i % 3),
                    "fan_rpm_max": 5600 + i * 15,
                },
            )

    def test_fetch_miner_chart_data(self):
        data = fetch_miner_chart_data(self.db_path, "23", hours=1.0, now_ts=self.now)
        self.assertEqual(data["miner_name"], "S19JPRO-23")
        self.assertEqual(data["threshold_ths"], 60.0)
        self.assertEqual(len(data["timestamps"]), 12)
        self.assertEqual(len(data["rates"]), 12)
        self.assertEqual(len(data["temps"]), 12)
        self.assertAlmostEqual(data["avg_rate"], 99.0, delta=1.5)
        self.assertGreaterEqual(data["max_temp"], 72.0)

    def test_render_miner_chart_png_validity(self):
        data = fetch_miner_chart_data(self.db_path, "23", hours=1.0, now_ts=self.now)
        png_bytes = render_miner_chart_png(data, hours=1.0)
        self.assertIsInstance(png_bytes, bytes)
        self.assertTrue(png_bytes.startswith(PNG_MAGIC_HEADER), "Output must be valid PNG image")
        self.assertGreater(len(png_bytes), 10_000, "Rendered chart must have non-trivial binary size")

    def test_fetch_and_render_fleet_chart_png(self):
        configured = [
            {"name": "S19JPRO-23", "host": "192.168.100.23"},
            {"name": "S19JPRO-24", "host": "192.168.100.24"},
        ]
        fleet_data = fetch_fleet_chart_data(self.db_path, configured, hours=1.0)
        self.assertIn("series", fleet_data)
        self.assertEqual(len(fleet_data["series"]), 2)
        
        png_bytes = render_fleet_chart_png(fleet_data, hours=1.0)
        self.assertIsInstance(png_bytes, bytes)
        self.assertTrue(png_bytes.startswith(PNG_MAGIC_HEADER))
        self.assertGreater(len(png_bytes), 15_000)

    def test_empty_dataset_handling(self):
        data = fetch_miner_chart_data(self.db_path, "99", hours=1.0)
        self.assertEqual(len(data["timestamps"]), 0)
        self.assertEqual(data["count"], 0)


from unittest.mock import MagicMock, patch
import threading
from app.miner_monitor import send_telegram_photo, _handle_callback_query, MinerState
from app.telegram_callbacks import CallbackTokenRegistry


class TestTelegramPhotoAndCallback(unittest.TestCase):
    @patch("requests.Session.post")
    def test_send_telegram_photo(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok = send_telegram_photo("bot123", "1206728163", b"dummy_png_bytes", caption="Test Chart")
        self.assertTrue(ok)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertIn("data", call_kwargs[1])
        self.assertEqual(call_kwargs[1]["data"]["chat_id"], "1206728163")
        self.assertEqual(call_kwargs[1]["data"]["caption"], "Test Chart")
        self.assertIn("photo", call_kwargs[1]["files"])

    @patch("app.miner_monitor.send_telegram_photo")
    @patch("app.miner_monitor.answer_callback_query")
    def test_chart_callback_query_dispatch(self, mock_answer_cb, mock_send_photo):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "test.db"
        store = EventStore(db_path)
        store.record_sample(
            observed_ts=time.time(),
            miner_key="S19JPRO-23|192.168.100.23:4028",
            miner_name="S19JPRO-23",
            host="192.168.100.23",
            state="OK",
            responded=True,
            rate_ths=98.5,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            elapsed_seconds=1000,
            telemetry={"max_temp_c": 75.0, "fan_rpm_max": 5800},
        )
        store.close()

        config = {
            "telegram": {"bot_token": "token", "chat_id": 1206728163},
            "miners": [{"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028}],
            "db_path": str(db_path),
        }
        cb_query = {
            "id": "cb_chart_1",
            "from": {"id": 1206728163},
            "data": "chart:23",
            "message": {"message_id": 42, "chat": {"id": 1206728163}},
        }
        registry = CallbackTokenRegistry()

        _handle_callback_query(
            cb_query,
            config=config,
            bot_token="token",
            chat_id="1206728163",
            miners=config["miners"],
            states={"S19JPRO-23|192.168.100.23:4028": MinerState()},
            state_lock=threading.Lock(),
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=registry,
        )
        mock_answer_cb.assert_called_once()
        mock_send_photo.assert_called_once()
        self.assertIn("S19JPRO-23", mock_send_photo.call_args[1]["caption"])
        temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
