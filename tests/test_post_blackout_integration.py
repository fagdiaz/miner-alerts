"""Integration tests for Post-Blackout Recovery Guard (Spec 050).

Validates end-to-end interactions between:
- Telegram callback dispatcher routing (pbr:resume:all, pbr:resume:<id>, pbr:snooze:60)
- Parallel resume and fan restoration routines
- State persistence and event recording
- Auto-resume lifecycle
"""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.governance.fleet_shutdown import OperationResult
from app.governance.post_blackout_guard import (
    PostBlackoutTracker,
    execute_post_blackout_cycle,
    render_recovery_action_card,
)
from app.miner_monitor import (
    MinerState,
    _handle_callback_query,
    load_state,
    save_state,
)
from app.telegram.callbacks import CallbackTokenRegistry


class TestPostBlackoutIntegration(unittest.TestCase):
    """End-to-end integration test suite for Spec 050."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028},
        ]
        self.states = {}
        for m in self.miners:
            sk = f"{m['name']}|{m['host']}:{m['port']}"
            st = MinerState()
            st.last_miner_state = "stopped"
            st.last_rate_ths = 0.0
            st.last_uptime_seconds = 180
            st.last_max_chip_temp = 35.0
            self.states[sk] = st

        self.state_lock = threading.Lock()
        self.token_registry = CallbackTokenRegistry()
        self.config = {
            "chat_id": "1206728163",
            "vnish_api_password": "admin",
            "post_blackout_guard": {
                "enabled": True,
                "confirm_ticks": 2,
                "auto_resume": False,
                "grace_period_seconds": 180,
            },
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.governance.post_blackout_guard.execute_parallel_fan_duty")
    @patch("app.governance.post_blackout_guard.execute_parallel_resume")
    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_pbr_resume_all_callback_flow(
        self, mock_answer, mock_edit, mock_resume, mock_fan
    ):
        """Verify pbr:resume:all callback executes parallel resume and fan restore."""
        mock_resume.return_value = {
            "23": OperationResult("23", True),
            "24": OperationResult("24", True),
            "25": OperationResult("25", True),
            "26": OperationResult("26", True),
        }
        mock_fan.return_value = {
            "23": OperationResult("23", True),
            "24": OperationResult("24", True),
            "25": OperationResult("25", True),
            "26": OperationResult("26", True),
        }

        # Set miners in maintenance/snooze to test clearing
        for st in self.states.values():
            st.is_shutdown_maintenance = True
            st.snooze_until_ts = time.time() + 3600.0

        save_state(self.state_path, self.states, 1)

        cb_query = {
            "id": "cb_pbr_1",
            "from": {"id": 1206728163},
            "data": "pbr:resume:all",
            "message": {"message_id": 999, "chat": {"id": 1206728163}},
        }

        mock_event_store = MagicMock()
        _handle_callback_query(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_bot_token",
            chat_id="1206728163",
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=mock_event_store,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )

        mock_answer.assert_called_once()
        mock_resume.assert_called_once()
        mock_fan.assert_called_once()
        mock_edit.assert_called_once()

        # Check state cleared
        for st in self.states.values():
            self.assertFalse(st.is_shutdown_maintenance)
            self.assertIsNone(st.snooze_until_ts)

    @patch("app.governance.post_blackout_guard.execute_parallel_fan_duty")
    @patch("app.governance.post_blackout_guard.execute_parallel_resume")
    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_pbr_resume_single_miner_callback_flow(
        self, mock_answer, mock_edit, mock_resume, mock_fan
    ):
        """Verify pbr:resume:23 targets only miner 23."""
        mock_resume.return_value = {"23": OperationResult("23", True)}
        mock_fan.return_value = {"23": OperationResult("23", True)}

        cb_query = {
            "id": "cb_pbr_2",
            "from": {"id": 1206728163},
            "data": "pbr:resume:23",
            "message": {"message_id": 1000, "chat": {"id": 1206728163}},
        }

        _handle_callback_query(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_bot_token",
            chat_id="1206728163",
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )

        mock_answer.assert_called_once()
        mock_resume.assert_called_once()
        call_miners = mock_resume.call_args[0][0]
        self.assertEqual(len(call_miners), 1)
        self.assertEqual(call_miners[0]["name"], "S19JPRO-23")

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_pbr_snooze_callback_flow(self, mock_answer, mock_edit):
        """Verify pbr:snooze:60 snoozes all miners."""
        cb_query = {
            "id": "cb_pbr_3",
            "from": {"id": 1206728163},
            "data": "pbr:snooze:60",
            "message": {"message_id": 1001, "chat": {"id": 1206728163}},
        }

        _handle_callback_query(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_bot_token",
            chat_id="1206728163",
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )

        mock_answer.assert_called_once()
        mock_edit.assert_called_once()
        for st in self.states.values():
            self.assertIsNotNone(st.snooze_until_ts)
            self.assertGreater(st.snooze_until_ts, time.time())

    @patch("app.governance.fleet_shutdown.execute_parallel_fan_duty")
    @patch("app.governance.fleet_shutdown.execute_parallel_resume")
    def test_full_cycle_alert_and_auto_resume(self, mock_resume, mock_fan):
        """Simulate monitor tick execution with auto-resume."""
        mock_send = MagicMock()
        mock_resume.return_value = {
            "23": OperationResult("23", True),
            "24": OperationResult("24", True),
            "25": OperationResult("25", True),
            "26": OperationResult("26", True),
        }
        mock_fan.return_value = {
            "23": OperationResult("23", True),
            "24": OperationResult("24", True),
            "25": OperationResult("25", True),
            "26": OperationResult("26", True),
        }

        tracker = PostBlackoutTracker()
        cfg = {
            "post_blackout_guard": {
                "enabled": True,
                "confirm_ticks": 2,
                "auto_resume": True,
                "grace_period_seconds": 60.0,
            },
            "startup_safety_guard_seconds": 0.0,
        }

        # Tick 1: candidate detected, ticks=1 < 2
        r1 = execute_post_blackout_cycle(
            self.miners, self.states, self.state_lock, cfg,
            now_ts=1000.0, process_start_ts=900.0, tracker=tracker,
            send_telegram_fn=mock_send,
        )
        mock_send.assert_not_called()

        # Tick 2: confirmed, ticks=2 >= 2 -> Telegram alert dispatched
        r2 = execute_post_blackout_cycle(
            self.miners, self.states, self.state_lock, cfg,
            now_ts=1030.0, process_start_ts=900.0, tracker=tracker,
            send_telegram_fn=mock_send, bot_token="tok", chat_id="123",
        )
        self.assertEqual(len(r2["candidates"]), 4)
        mock_send.assert_called_once()

        # Tick 3: grace period (60s) elapsed (now=1065 > 1000 + 60) -> Auto-resume executed!
        mock_send.reset_mock()
        r3 = execute_post_blackout_cycle(
            self.miners, self.states, self.state_lock, cfg,
            now_ts=1065.0, process_start_ts=900.0, tracker=tracker,
            send_telegram_fn=mock_send, bot_token="tok", chat_id="123",
            resume_fn=mock_resume, fan_fn=mock_fan,
        )
        mock_resume.assert_called_once()
        mock_fan.assert_called_once()
        self.assertEqual(len(r3["auto_resumed"]), 4)
        mock_send.assert_called_once()  # Auto-resume notification card sent


if __name__ == "__main__":
    unittest.main()
