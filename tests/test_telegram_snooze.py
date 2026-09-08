"""Unit tests for Miner Maintenance Snooze (Spec 033)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import time
from pathlib import Path
import threading
from dataclasses import dataclass, field
from typing import Optional

from app.telegram_snooze import (
    parse_snooze_args,
    is_miner_snoozed,
    get_snooze_remaining_seconds,
    format_snooze_remaining,
    format_snooze_expiry_time,
    format_snooze_tag,
    build_snooze_status_text,
    DEFAULT_SNOOZE_MINUTES,
    MIN_SNOOZE_MINUTES,
    MAX_SNOOZE_MINUTES,
)


@dataclass
class DummyMinerState:
    snooze_until_ts: Optional[float] = None
    low_streak: int = 0
    offline_streak: int = 0
    ok_streak: int = 0
    reboot_pending_until: float = 0.0
    last_reboot_ts: float = 0.0


class TestTelegramSnooze(unittest.TestCase):
    def test_parse_snooze_args_defaults(self):
        target, minutes = parse_snooze_args("")
        self.assertIsNone(target)
        self.assertEqual(minutes, DEFAULT_SNOOZE_MINUTES)

        target, minutes = parse_snooze_args("23")
        self.assertEqual(target, "23")
        self.assertEqual(minutes, 60.0)

    def test_parse_snooze_args_custom_minutes(self):
        target, minutes = parse_snooze_args("23 45")
        self.assertEqual(target, "23")
        self.assertEqual(minutes, 45.0)

        target, minutes = parse_snooze_args("all 120m")
        self.assertEqual(target, "all")
        self.assertEqual(minutes, 120.0)

        target, minutes = parse_snooze_args("fleet 30min")
        self.assertEqual(target, "fleet")
        self.assertEqual(minutes, 30.0)

        target, minutes = parse_snooze_args("23 2h")
        self.assertEqual(target, "23")
        self.assertEqual(minutes, 120.0)

    def test_parse_snooze_args_clamping(self):
        # Under minimum (< 1 min)
        target, minutes = parse_snooze_args("23 0")
        self.assertEqual(minutes, MIN_SNOOZE_MINUTES)

        # Over maximum (> 1440 min / 24h)
        target, minutes = parse_snooze_args("23 5000")
        self.assertEqual(minutes, MAX_SNOOZE_MINUTES)

        # Invalid number defaults to 60.0
        target, minutes = parse_snooze_args("23 abc")
        self.assertEqual(minutes, 60.0)

    def test_is_miner_snoozed(self):
        st = DummyMinerState()
        self.assertFalse(is_miner_snoozed(st, now_ts=1000.0))
        self.assertFalse(is_miner_snoozed(None, now_ts=1000.0))

        # Active future timestamp
        st.snooze_until_ts = 1500.0
        self.assertTrue(is_miner_snoozed(st, now_ts=1000.0))

        # Exactly at boundary
        self.assertFalse(is_miner_snoozed(st, now_ts=1500.0))

        # Expired past timestamp
        self.assertFalse(is_miner_snoozed(st, now_ts=1600.0))

    def test_get_snooze_remaining_seconds(self):
        st = DummyMinerState(snooze_until_ts=1300.0)
        self.assertEqual(get_snooze_remaining_seconds(st, now_ts=1000.0), 300.0)
        self.assertEqual(get_snooze_remaining_seconds(st, now_ts=1350.0), 0.0)
        self.assertEqual(get_snooze_remaining_seconds(None, now_ts=1000.0), 0.0)

    def test_format_snooze_remaining(self):
        self.assertEqual(format_snooze_remaining(0.0), "0m")
        self.assertEqual(format_snooze_remaining(-10.0), "0m")
        self.assertEqual(format_snooze_remaining(30.0), "< 1m")
        self.assertEqual(format_snooze_remaining(60.0), "1m")
        self.assertEqual(format_snooze_remaining(2700.0), "45m")
        self.assertEqual(format_snooze_remaining(3600.0), "1h")
        self.assertEqual(format_snooze_remaining(4500.0), "1h 15m")
        self.assertEqual(format_snooze_remaining(7200.0), "2h")

    def test_format_snooze_tag(self):
        st = DummyMinerState(snooze_until_ts=1000.0 + 2700.0)
        self.assertEqual(format_snooze_tag(st, now_ts=1000.0), " [🔕 Silenciado: 45m]")

        # Expired
        self.assertEqual(format_snooze_tag(st, now_ts=5000.0), "")
        self.assertEqual(format_snooze_tag(None, now_ts=1000.0), "")

    def test_build_snooze_status_text(self):
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
        ]
        states = {
            "S19JPRO-23|192.168.1.23:4028": DummyMinerState(),
            "S19JPRO-24|192.168.1.24:4028": DummyMinerState(),
        }

        # None snoozed
        text = build_snooze_status_text(miners, states, now_ts=1000.0)
        self.assertIn("No hay mineros silenciados actualmente", text)

        # One snoozed
        states["S19JPRO-23|192.168.1.23:4028"].snooze_until_ts = 1000.0 + 3600.0
        text = build_snooze_status_text(miners, states, now_ts=1000.0)
        self.assertIn("Mineros en Mantenimiento", text)
        self.assertIn("S19JPRO-23 (23): resta 1h", text)
        self.assertNotIn("S19JPRO-24", text)

    def test_filter_snoozed_episodes(self):
        from app.telegram_snooze import filter_snoozed_episodes
        from app.alert_episodes import EpisodeNotificationBatch

        ep23 = MagicMock(miner_key="S19JPRO-23|192.168.1.23:4028", name_display="23")
        ep24 = MagicMock(miner_key="S19JPRO-24|192.168.1.24:4028", name_display="24")
        batch = EpisodeNotificationBatch(opened=[ep23, ep24], persistent=[], recovered=[])

        states = {
            "S19JPRO-23|192.168.1.23:4028": DummyMinerState(snooze_until_ts=2000.0),  # Snoozed
            "S19JPRO-24|192.168.1.24:4028": DummyMinerState(snooze_until_ts=None),    # Not snoozed
        }

        filtered = filter_snoozed_episodes(batch, states, now_ts=1000.0)
        self.assertEqual(len(filtered.opened), 1)
        self.assertEqual(filtered.opened[0].name_display, "24")

    def test_auto_reboot_suppressed_when_snoozed(self):
        now_ts = 1000.0
        reboot_cooldown_seconds = 900.0
        st = DummyMinerState(
            snooze_until_ts=2000.0,  # Snoozed!
            reboot_pending_until=950.0,
            last_reboot_ts=0.0,
        )

        reboot_names_tick = []
        is_snoozed = is_miner_snoozed(st, now_ts)
        new_state = "LOW"

        if (
            not is_snoozed
            and st.reboot_pending_until
            and new_state in ("LOW", "OFFLINE")
            and (now_ts - st.last_reboot_ts) >= reboot_cooldown_seconds
        ):
            reboot_names_tick.append("S19JPRO-23")

        self.assertEqual(reboot_names_tick, [])
        self.assertTrue(is_snoozed)



class TestTelegramSnoozeIntegration(unittest.TestCase):
    def setUp(self):
        from app.telegram_callbacks import CallbackTokenRegistry
        from app.miner_monitor import MinerState

        self.bot_token = "TEST_BOT_TOKEN"
        self.chat_id = "1206728163"
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
        ]
        self.states = {
            "S19JPRO-23|192.168.1.23:4028": MinerState(),
            "S19JPRO-24|192.168.1.24:4028": MinerState(),
        }
        self.state_lock = threading.Lock()
        self.token_registry = CallbackTokenRegistry()

    @patch("app.miner_monitor.edit_message_reply_markup")
    @patch("app.miner_monitor.answer_callback_query")
    def test_snz_callback_flow(self, mock_answer_cb, mock_edit_markup):
        from app.miner_monitor import _handle_callback_query

        cb_query = {
            "id": "cb_snz_1",
            "from": {"id": 1206728163},
            "data": "snz:23:60",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }

        now_before = time.time()
        _handle_callback_query(
            cb_query,
            config={},
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("data/state.test.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.token_registry,
        )

        mock_answer_cb.assert_called_once()
        self.assertIn("silenciado", mock_answer_cb.call_args[1].get("text", "").lower())

        mock_edit_markup.assert_called_once()
        markup = mock_edit_markup.call_args[0][3]
        self.assertIn("Silenciado", markup["inline_keyboard"][0][0]["text"])

        st = self.states["S19JPRO-23|192.168.1.23:4028"]
        self.assertIsNotNone(st.snooze_until_ts)
        self.assertGreater(st.snooze_until_ts, now_before + 3500)

    def test_save_and_load_state_preserves_snooze(self):
        import tempfile
        from app.miner_monitor import save_state, load_state, MinerState

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            states = {
                "S19JPRO-23|192.168.1.23:4028": MinerState(snooze_until_ts=1750000000.0),
                "S19JPRO-24|192.168.1.24:4028": MinerState(snooze_until_ts=None),
            }
            save_state(state_file, states, last_update_id=42)
            loaded_states, last_id = load_state(state_file)
            self.assertEqual(last_id, 42)
            self.assertIn("S19JPRO-23|192.168.1.23:4028", loaded_states)
            self.assertEqual(
                loaded_states["S19JPRO-23|192.168.1.23:4028"].snooze_until_ts,
                1750000000.0,
            )
            self.assertIsNone(loaded_states["S19JPRO-24|192.168.1.24:4028"].snooze_until_ts)


if __name__ == "__main__":
    unittest.main()

