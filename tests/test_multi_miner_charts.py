"""Unit and integration test suite for Spec 064: Multi-Miner Charts & Interactive Range Selector.

Covers:
- Group chart data fetching & dual-subplot PNG rendering.
- Inline keyboard generation (1h, 6h, 24h, 7d) with active range indicators.
- Callback parsing and formatting for chart_range.
- edit_telegram_photo helper with editMessageMedia and multipart/form-data.
- In-place callback query dispatch for miners, electrical groups, and fleet.
- ChartCommand handling of electrical groups and 7d horizons.
- Matplotlib memory hygiene: 100 consecutive renders with zero leaked figures.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import matplotlib.pyplot as plt

from app.core.event_store import EventStore
from app.miner_monitor import (
    MinerState,
    _handle_callback_query,
    edit_telegram_photo,
    send_telegram_photo,
)
from app.telegram.callbacks import (
    CallbackAction,
    CallbackTokenRegistry,
    build_callback_data,
    parse_callback_data,
)
from app.telegram.charts import (
    build_chart_range_keyboard,
    fetch_fleet_chart_data,
    fetch_group_chart_data,
    fetch_miner_chart_data,
    render_fleet_chart_png,
    render_group_chart_png,
    render_miner_chart_png,
)
from app.telegram.commands.diagnostics import ChartCommand
from app.telegram.context import TelegramRequestContext

PNG_MAGIC_HEADER = b"\x89PNG\r\n\x1a\n"


class TestMultiMinerCharts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_multi_charts.db"
        self.store = EventStore(self.db_path)
        self.now = time.time()
        self._populate_fixtures()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()
        plt.close("all")

    def _populate_fixtures(self):
        # 4 miners in 2 electrical groups:
        # elevator_1: S19JPRO-23, S19JPRO-24
        # elevator_2: S19JPRO-25, S19JPRO-26
        miners_info = [
            ("S19JPRO-23", "192.168.100.23", 98.0, 72.0, 5800),
            ("S19JPRO-24", "192.168.100.24", 95.0, 71.0, 5600),
            ("S19JPRO-25", "192.168.100.25", 102.0, 74.0, 6000),
            ("S19JPRO-26", "192.168.100.26", 99.0, 73.0, 5900),
        ]
        for i in range(12):
            ts = self.now - (12 - i) * 300.0  # 5 min intervals
            for name, host, base_rate, base_temp, base_fan in miners_info:
                self.store.record_sample(
                    observed_ts=ts,
                    miner_key=f"{name}|{host}:4028",
                    miner_name=name,
                    host=host,
                    state="OK",
                    responded=True,
                    rate_ths=base_rate + (i % 3) * 0.5,
                    threshold_ths=60.0,
                    active_boards=3,
                    expected_boards=3,
                    elapsed_seconds=1000 + i * 300,
                    telemetry={
                        "max_temp_c": base_temp + (i % 4) * 0.5,
                        "fan_rpm_max": base_fan + i * 10,
                    },
                )

        self.configured_miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
        ]

    # --- Phase A Tests: Group Charts & Diagnostics ---

    def test_fetch_group_chart_data_matches_correct_miners(self):
        data_el1 = fetch_group_chart_data(self.db_path, "elevator_1", self.configured_miners, hours=1.0, now_ts=self.now)
        self.assertEqual(data_el1["group_name"], "elevator_1")
        self.assertEqual(data_el1["count"], 2)
        self.assertEqual(data_el1["total_miners"], 2)
        series_names = [s["miner_name"] for s in data_el1["series"]]
        self.assertIn("S19JPRO-23", series_names)
        self.assertIn("S19JPRO-24", series_names)

        data_el2 = fetch_group_chart_data(self.db_path, "elevator_2", self.configured_miners, hours=1.0, now_ts=self.now)
        self.assertEqual(data_el2["count"], 2)
        series_names_2 = [s["miner_name"] for s in data_el2["series"]]
        self.assertIn("S19JPRO-25", series_names_2)
        self.assertIn("S19JPRO-26", series_names_2)

    def test_fetch_group_chart_data_empty_when_no_match(self):
        data = fetch_group_chart_data(self.db_path, "nonexistent_group", self.configured_miners, hours=1.0, now_ts=self.now)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["total_miners"], 0)
        self.assertEqual(len(data["series"]), 0)

    def test_render_group_chart_png_validity(self):
        data = fetch_group_chart_data(self.db_path, "elevator_1", self.configured_miners, hours=1.0, now_ts=self.now)
        png_bytes = render_group_chart_png(data, hours=1.0)
        self.assertIsInstance(png_bytes, bytes)
        self.assertTrue(png_bytes.startswith(PNG_MAGIC_HEADER))
        self.assertGreater(len(png_bytes), 15_000)

    def test_render_group_chart_png_raises_on_empty(self):
        empty_data = {"group_name": "elevator_empty", "count": 0, "series": []}
        with self.assertRaises(ValueError):
            render_group_chart_png(empty_data, hours=1.0)

    # --- Phase B Tests: Keyboard & In-place Updates ---

    def test_build_chart_range_keyboard_marks_active_button(self):
        # 1h active
        kb_1h = build_chart_range_keyboard("23", current_hours=1.0)
        row = kb_1h["inline_keyboard"][0]
        self.assertEqual(len(row), 4)
        self.assertEqual(row[0]["text"], "• 1h •")
        self.assertEqual(row[0]["callback_data"], "chart_range:23:1")
        self.assertEqual(row[1]["text"], "6h")
        self.assertEqual(row[1]["callback_data"], "chart_range:23:6")
        self.assertEqual(row[2]["text"], "24h")
        self.assertEqual(row[2]["callback_data"], "chart_range:23:24")
        self.assertEqual(row[3]["text"], "7d")
        self.assertEqual(row[3]["callback_data"], "chart_range:23:168")

        # 24h active on group
        kb_24h = build_chart_range_keyboard("elevator_1", current_hours=24.0)
        row_24h = kb_24h["inline_keyboard"][0]
        self.assertEqual(row_24h[2]["text"], "• 24h •")
        self.assertEqual(row_24h[2]["callback_data"], "chart_range:elevator_1:24")

        # 7d active on fleet
        kb_7d = build_chart_range_keyboard("fleet", current_hours=168.0)
        row_7d = kb_7d["inline_keyboard"][0]
        self.assertEqual(row_7d[3]["text"], "• 7d •")
        self.assertEqual(row_7d[3]["callback_data"], "chart_range:fleet:168")

        # Full name prefix stripped
        kb_strip = build_chart_range_keyboard("S19JPRO-23", current_hours=1.0)
        self.assertEqual(kb_strip["inline_keyboard"][0][0]["callback_data"], "chart_range:23:1")

    def test_callbacks_grammar_and_parsing(self):
        # Parse
        action = parse_callback_data("chart_range:23:6")
        self.assertIsNotNone(action)
        self.assertEqual(action.action_type, "chart_range")
        self.assertEqual(action.miner_id, "23")
        self.assertEqual(action.param, "6")

        action_grp = parse_callback_data("chart_range:elevator_1:24")
        self.assertEqual(action_grp.action_type, "chart_range")
        self.assertEqual(action_grp.miner_id, "elevator_1")
        self.assertEqual(action_grp.param, "24")

        action_fleet = parse_callback_data("chart_range:fleet:168")
        self.assertEqual(action_fleet.action_type, "chart_range")
        self.assertEqual(action_fleet.miner_id, "fleet")
        self.assertEqual(action_fleet.param, "168")

        # Build
        raw = build_callback_data("chart_range", "23", param="6")
        self.assertEqual(raw, "chart_range:23:6")
        self.assertLessEqual(len(raw.encode("utf-8")), 64)

    @patch("requests.Session.post")
    def test_edit_telegram_photo_api_call(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        kb = build_chart_range_keyboard("23", current_hours=6.0)
        ok = edit_telegram_photo(
            "fake_token",
            "1206728163",
            42,
            b"fake_png_data",
            caption="Test Caption",
            reply_markup=kb,
        )
        self.assertTrue(ok)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertIn("editMessageMedia", call_kwargs[0][0])
        self.assertEqual(call_kwargs[1]["data"]["chat_id"], "1206728163")
        self.assertEqual(call_kwargs[1]["data"]["message_id"], 42)
        media_payload = json.loads(call_kwargs[1]["data"]["media"])
        self.assertEqual(media_payload["type"], "photo")
        self.assertEqual(media_payload["media"], "attach://file_0")
        self.assertEqual(media_payload["caption"], "Test Caption")
        self.assertIn("file_0", call_kwargs[1]["files"])

    @patch("requests.Session.post")
    def test_send_telegram_photo_with_reply_markup(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        kb = build_chart_range_keyboard("fleet", current_hours=1.0)
        ok = send_telegram_photo(
            "fake_token",
            "1206728163",
            b"fake_png_data",
            caption="Fleet Chart",
            reply_markup=kb,
        )
        self.assertTrue(ok)
        call_kwargs = mock_post.call_args
        self.assertIn("reply_markup", call_kwargs[1]["data"])
        parsed_kb = json.loads(call_kwargs[1]["data"]["reply_markup"])
        self.assertEqual(len(parsed_kb["inline_keyboard"][0]), 4)

    @patch("app.miner_monitor.edit_telegram_photo")
    @patch("app.miner_monitor.answer_callback_query")
    def test_handle_callback_query_chart_range_dispatch(self, mock_answer_cb, mock_edit_photo):
        mock_edit_photo.return_value = True
        config = {
            "telegram": {"bot_token": "token", "chat_id": 1206728163},
            "miners": self.configured_miners,
            "db_path": str(self.db_path),
        }
        registry = CallbackTokenRegistry()

        # 1. Update single miner range
        cb_query = {
            "id": "cb_range_1",
            "from": {"id": 1206728163},
            "data": "chart_range:23:6",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=config,
            bot_token="token",
            chat_id="1206728163",
            miners=config["miners"],
            states={"S19JPRO-23|192.168.100.23:4028": MinerState()},
            state_lock=threading.Lock(),
            state_path=Path(self.temp_dir.name) / "state.json",
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=self.store,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=registry,
        )
        mock_edit_photo.assert_called_once()
        mock_answer_cb.assert_called_once()
        self.assertIn("Rango actualizado: 6h", mock_answer_cb.call_args[1]["text"])

        # 2. Update group range
        mock_edit_photo.reset_mock()
        mock_answer_cb.reset_mock()
        cb_query_grp = {
            "id": "cb_range_2",
            "from": {"id": 1206728163},
            "data": "chart_range:elevator_1:24",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query_grp,
            config=config,
            bot_token="token",
            chat_id="1206728163",
            miners=config["miners"],
            states={},
            state_lock=threading.Lock(),
            state_path=Path(self.temp_dir.name) / "state.json",
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=self.store,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=registry,
        )
        mock_edit_photo.assert_called_once()
        self.assertIn("ELEVATOR_1", mock_edit_photo.call_args[1]["caption"])
        self.assertIn("Rango actualizado: 24h", mock_answer_cb.call_args[1]["text"])

        # 3. Update fleet range to 7d
        mock_edit_photo.reset_mock()
        mock_answer_cb.reset_mock()
        cb_query_fleet = {
            "id": "cb_range_3",
            "from": {"id": 1206728163},
            "data": "chart_range:fleet:168",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query_fleet,
            config=config,
            bot_token="token",
            chat_id="1206728163",
            miners=config["miners"],
            states={},
            state_lock=threading.Lock(),
            state_path=Path(self.temp_dir.name) / "state.json",
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=self.store,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=registry,
        )
        mock_edit_photo.assert_called_once()
        self.assertIn("Flota completa", mock_edit_photo.call_args[1]["caption"])
        self.assertIn("Rango actualizado: 7d", mock_answer_cb.call_args[1]["text"])

    @patch("app.miner_monitor.send_telegram_photo")
    def test_chart_command_group_handling(self, mock_send_photo):
        handler = ChartCommand()
        config = {
            "telegram": {"bot_token": "token", "chat_id": 1206728163},
            "miners": self.configured_miners,
            "db_path": str(self.db_path),
        }
        mock_send = MagicMock()
        ctx = TelegramRequestContext(
            bot_token="token",
            chat_id="1206728163",
            config=config,
            miners=self.configured_miners,
            states={},
            state_lock=threading.Lock(),
            state_path=Path(self.temp_dir.name) / "state.json",
            event_store=self.store,
        )
        ctx.send_message = mock_send

        # /chart elevator_1
        ok = handler.handle(ctx, ["elevator_1"])
        self.assertTrue(ok)
        mock_send_photo.assert_called_once()
        caption = mock_send_photo.call_args[1]["caption"]
        self.assertIn("ELEVATOR_1", caption)
        self.assertIn("reply_markup", mock_send_photo.call_args[1])

        # /chart unknown_target -> message with available miners & groups
        mock_send_photo.reset_mock()
        ok_unknown = handler.handle(ctx, ["unknown_target"])
        self.assertTrue(ok_unknown)
        mock_send.assert_called_once()
        err_msg = mock_send.call_args[0][0]
        self.assertIn("no encontrado", err_msg)
        self.assertIn("Grupos:", err_msg)

    # --- Phase C Tests: Memory Stability Test ---

    def test_matplotlib_memory_hygiene_100_renders(self):
        """Perform 100 consecutive renders across miner, group, and fleet charts.

        Asserts that plt.get_fignums() is always empty after each render,
        preventing figure retention leaks in long-running services.
        """
        miner_data = fetch_miner_chart_data(self.db_path, "23", hours=1.0, now_ts=self.now)
        group_data = fetch_group_chart_data(self.db_path, "elevator_1", self.configured_miners, hours=1.0, now_ts=self.now)
        fleet_data = fetch_fleet_chart_data(self.db_path, self.configured_miners, hours=1.0, now_ts=self.now)

        for i in range(100):
            if i % 3 == 0:
                png = render_miner_chart_png(miner_data, hours=1.0)
            elif i % 3 == 1:
                png = render_group_chart_png(group_data, hours=1.0)
            else:
                png = render_fleet_chart_png(fleet_data, hours=1.0)

            self.assertTrue(png.startswith(PNG_MAGIC_HEADER))
            # Critical verification: figure must be explicitly closed, zero leaked figures in matplotlib manager
            open_figs = plt.get_fignums()
            self.assertEqual(
                open_figs,
                [],
                f"Matplotlib figure leaked on iteration {i}: open figures = {open_figs}",
            )


if __name__ == "__main__":
    unittest.main()
