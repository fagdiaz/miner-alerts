"""Unit tests for Post-Blackout Recovery Guard (Spec 050)."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from app.governance.fleet_shutdown import OperationResult
from app.governance.post_blackout_guard import (
    DEFAULT_CONFIRM_TICKS,
    DEFAULT_MAX_CHIP_TEMP_C,
    PostBlackoutTarget,
    PostBlackoutTracker,
    evaluate_miner_post_blackout,
    execute_post_blackout_cycle,
    format_uptime_short,
    is_stopped_state,
    is_transient_state,
    process_post_blackout_callback,
    render_post_blackout_alert,
    render_recovery_action_card,
    resolve_target_miners,
)
from app.telegram.help_center import visible_line_width


class TestPostBlackoutEvaluator(unittest.TestCase):
    """Test pure domain logic for post-blackout candidate evaluation."""

    def test_transient_states(self):
        for st in ("starting", "benchmarking", "init", "initializing", "rebooting"):
            self.assertTrue(is_transient_state(st))
            ok, reason = evaluate_miner_post_blackout(
                miner_id="23",
                name="S19JPRO-23",
                host="192.168.1.23",
                miner_state=st,
                rate_ths=0.0,
                uptime_seconds=60,
                consecutive_stopped_ticks=3,
            )
            self.assertFalse(ok)
            self.assertEqual(reason, "transient_starting")

    def test_active_mining_ignored(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="mining",
            rate_ths=98.5,
            uptime_seconds=3600,
            consecutive_stopped_ticks=0,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "active_or_normal")

    def test_maintenance_interlock(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=300,
            consecutive_stopped_ticks=5,
            in_maintenance=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "in_maintenance")

    def test_snooze_interlock(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=300,
            consecutive_stopped_ticks=5,
            is_snoozed=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "snoozed")

    def test_startup_guard_interlock(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=300,
            consecutive_stopped_ticks=5,
            startup_guard_active=True,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "startup_guard_active")

    def test_thermal_interlock(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=300,
            consecutive_stopped_ticks=5,
            chip_temp_c=86.5,
            max_chip_temp_c=85.0,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "thermal_interlock")

    def test_awaiting_confirmation_ticks(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=120,
            consecutive_stopped_ticks=1,
            confirm_ticks=2,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "awaiting_confirmation")

    def test_valid_stopped_candidate(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="23",
            name="S19JPRO-23",
            host="192.168.1.23",
            miner_state="stopped",
            rate_ths=0.0,
            uptime_seconds=120,
            consecutive_stopped_ticks=2,
            confirm_ticks=2,
            chip_temp_c=32.0,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_valid_paused_candidate(self):
        ok, reason = evaluate_miner_post_blackout(
            miner_id="24",
            name="S19JPRO-24",
            host="192.168.1.24",
            miner_state="paused",
            rate_ths=0.0,
            uptime_seconds=240,
            consecutive_stopped_ticks=3,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)


class TestUptimeFormatting(unittest.TestCase):
    """Test compact uptime formatter."""

    def test_format_uptime_short(self):
        self.assertEqual(format_uptime_short(None), "N/D")
        self.assertEqual(format_uptime_short(-10), "N/D")
        self.assertEqual(format_uptime_short(45), "45s")
        self.assertEqual(format_uptime_short(180), "3m")
        self.assertEqual(format_uptime_short(3600), "1h")
        self.assertEqual(format_uptime_short(3660), "1h 1m")
        self.assertEqual(format_uptime_short(86400), "1d 0h")
        self.assertEqual(format_uptime_short(90000), "1d 1h")


class TestPostBlackoutCardsMobileWidth(unittest.TestCase):
    """Test that all Telegram cards strictly comply with mobile width <= 32 cols."""

    def test_alert_card_multi_miners(self):
        targets = [
            PostBlackoutTarget(
                miner_id="23",
                name="S19JPRO-23",
                host="192.168.1.23",
                uptime_seconds=180,
                consecutive_stopped_ticks=2,
            ),
            PostBlackoutTarget(
                miner_id="24",
                name="S19JPRO-24",
                host="192.168.1.24",
                uptime_seconds=185,
                consecutive_stopped_ticks=2,
            ),
        ]
        text, reply_markup = render_post_blackout_alert(targets, auto_resume_seconds=180)
        for line in text.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars ({w}): {line}")

        # Check keyboard
        kb = reply_markup["inline_keyboard"]
        self.assertEqual(len(kb), 2)
        self.assertEqual(kb[0][0]["callback_data"], "pbr:resume:all")
        self.assertIn("Flota (2)", kb[0][0]["text"])
        self.assertEqual(kb[1][0]["callback_data"], "pbr:snooze:60")

    def test_alert_card_single_miner_no_auto_resume(self):
        targets = [
            PostBlackoutTarget(
                miner_id="25",
                name="S19JPRO-25",
                host="192.168.1.25",
                uptime_seconds=300,
                consecutive_stopped_ticks=3,
            )
        ]
        text, reply_markup = render_post_blackout_alert(targets, auto_resume_seconds=None)
        for line in text.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars ({w}): {line}")

        kb = reply_markup["inline_keyboard"]
        self.assertEqual(kb[0][0]["callback_data"], "pbr:resume:25")
        self.assertIn("S19JPRO-25", kb[0][0]["text"])

    def test_recovery_action_cards(self):
        # Manual resume
        text_manual = render_recovery_action_card(["S19JPRO-23", "S19JPRO-24"], automated=False)
        for line in text_manual.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars ({w}): {line}")
        self.assertIn("FLOTA REANUDADA", text_manual)

        # Automated resume
        text_auto = render_recovery_action_card(["S19JPRO-23", "S19JPRO-24", "S19JPRO-25"], automated=True)
        for line in text_auto.split("\n"):
            w = visible_line_width(line)
            self.assertLessEqual(w, 32, f"Line exceeds 32 chars ({w}): {line}")
        self.assertIn("AUTO-REANUDACIÓN OK", text_auto)


class TestPostBlackoutTracker(unittest.TestCase):
    """Test state tracker increment, reset and flag management."""

    def test_tracker_lifecycle(self):
        tracker = PostBlackoutTracker()
        self.assertEqual(tracker.get_stopped_ticks("23"), 0)

        # First tick as candidate
        t1 = tracker.record_tick("23", True, now_ts=100.0)
        self.assertEqual(t1, 1)
        self.assertEqual(tracker.get_first_stopped_ts("23"), 100.0)
        self.assertFalse(tracker.is_alert_sent("23"))

        # Second tick
        t2 = tracker.record_tick("23", True, now_ts=130.0)
        self.assertEqual(t2, 2)
        self.assertEqual(tracker.get_first_stopped_ts("23"), 100.0)

        # Mark alert sent
        tracker.mark_alert_sent("23")
        self.assertTrue(tracker.is_alert_sent("23"))

        # Becomes active -> reset
        t3 = tracker.record_tick("23", False, now_ts=160.0)
        self.assertEqual(t3, 0)
        self.assertEqual(tracker.get_stopped_ticks("23"), 0)
        self.assertIsNone(tracker.get_first_stopped_ts("23"))
        self.assertFalse(tracker.is_alert_sent("23"))


class TestPostBlackoutOrchestration(unittest.TestCase):
    """Test cycle execution and callback dispatch."""

    def setUp(self):
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
        ]
        self.state_lock = threading.Lock()
        self.tracker = PostBlackoutTracker()

    def test_cycle_disabled_in_config(self):
        cfg = {"post_blackout_guard": {"enabled": False}}
        res = execute_post_blackout_cycle(
            self.miners, {}, self.state_lock, cfg, 1000.0, 500.0, self.tracker
        )
        self.assertEqual(res["status"], "disabled")

    def test_cycle_dispatches_alert_after_confirm_ticks(self):
        mock_send = MagicMock()
        mock_event = MagicMock()
        cfg = {
            "post_blackout_guard": {
                "enabled": True,
                "confirm_ticks": 2,
                "auto_resume": False,
            },
            "startup_safety_guard_seconds": 60.0,
        }
        # Simulate state for miner 23: stopped, 0 TH/s
        class DummyState:
            is_shutdown_maintenance = False
            snooze_until_ts = None
            last_miner_state = "stopped"
            last_rate_ths = 0.0
        class DummyMiningState:
            is_shutdown_maintenance = False
            snooze_until_ts = None
            last_miner_state = "mining"
            last_rate_ths = 95.0
            last_uptime_seconds = 3600
            last_max_chip_temp = 60.0

        states = {
            "S19JPRO-23|192.168.1.23:4028": DummyState(),
            "S19JPRO-24|192.168.1.24:4028": DummyMiningState(),
        }

        # Tick 1: candidate recorded (ticks=1 < confirm_ticks=2) -> no alert yet
        res1 = execute_post_blackout_cycle(
            self.miners,
            states,
            self.state_lock,
            cfg,
            now_ts=1000.0,
            process_start_ts=500.0,
            tracker=self.tracker,
            send_telegram_fn=mock_send,
        )
        self.assertEqual(res1["status"], "ok")
        mock_send.assert_not_called()

        # Tick 2: candidate confirmed (ticks=2 >= 2) -> alert sent!
        res2 = execute_post_blackout_cycle(
            self.miners,
            states,
            self.state_lock,
            cfg,
            now_ts=1030.0,
            process_start_ts=500.0,
            tracker=self.tracker,
            send_telegram_fn=mock_send,
            record_event_fn=mock_event,
            bot_token="token",
            chat_id="123",
        )
        self.assertEqual(res2["status"], "alerted")
        self.assertIn("23", res2["candidates"])
        mock_send.assert_called_once()
        mock_event.assert_called_once()

        # Tick 3: alert already sent -> no duplicate send
        mock_send.reset_mock()
        res3 = execute_post_blackout_cycle(
            self.miners,
            states,
            self.state_lock,
            cfg,
            now_ts=1060.0,
            process_start_ts=500.0,
            tracker=self.tracker,
            send_telegram_fn=mock_send,
        )
        mock_send.assert_not_called()

    def test_cycle_auto_resume_flow(self):
        mock_send = MagicMock()
        mock_resume = MagicMock(return_value={"23": OperationResult("23", True)})
        mock_fan = MagicMock()

        cfg = {
            "post_blackout_guard": {
                "enabled": True,
                "confirm_ticks": 1,
                "auto_resume": True,
                "grace_period_seconds": 60.0,
            },
            "startup_safety_guard_seconds": 0.0,
        }

        class DummyState:
            is_shutdown_maintenance = False
            snooze_until_ts = None
            last_miner_state = "stopped"
            last_rate_ths = 0.0
            last_uptime_seconds = 180
            last_max_chip_temp = 32.0

        states = {"S19JPRO-23|192.168.1.23:4028": DummyState()}

        # Cycle at t=1000: alert sent, first_stopped_ts = 1000
        execute_post_blackout_cycle(
            self.miners,
            states,
            self.state_lock,
            cfg,
            now_ts=1000.0,
            process_start_ts=900.0,
            tracker=self.tracker,
            send_telegram_fn=mock_send,
        )
        mock_resume.assert_not_called()

        # Cycle at t=1070: grace_period (60s) elapsed! Auto-resume triggers
        res = execute_post_blackout_cycle(
            self.miners,
            states,
            self.state_lock,
            cfg,
            now_ts=1070.0,
            process_start_ts=900.0,
            tracker=self.tracker,
            send_telegram_fn=mock_send,
            resume_fn=mock_resume,
            fan_fn=mock_fan,
        )
        mock_resume.assert_called_once()
        mock_fan.assert_called_once()
        self.assertIn("S19JPRO-23", res["auto_resumed"])

    def test_callback_resume_all_and_snooze(self):
        mock_ans = MagicMock()
        mock_edit = MagicMock()
        mock_save = MagicMock()
        mock_resume = MagicMock(return_value={
            "23": OperationResult("23", True),
            "24": OperationResult("24", True),
        })
        mock_fan = MagicMock()

        class DummyState:
            is_shutdown_maintenance = True
            snooze_until_ts = 9999.0

        states = {
            "S19JPRO-23|192.168.1.23:4028": DummyState(),
            "S19JPRO-24|192.168.1.24:4028": DummyState(),
        }

        # Test pbr:resume:all
        handled = process_post_blackout_callback(
            cb_data="pbr:resume:all",
            cb_id="cb_1",
            cb_chat_id=123,
            message_id=456,
            miners=self.miners,
            states=states,
            state_lock=self.state_lock,
            state_path="state.json",
            config={},
            bot_token="token",
            answer_cb_fn=mock_ans,
            edit_msg_fn=mock_edit,
            save_state_fn=mock_save,
            resume_fn=mock_resume,
            fan_fn=mock_fan,
            tracker=self.tracker,
        )
        self.assertTrue(handled)
        mock_resume.assert_called_once()
        mock_fan.assert_called_once()
        mock_edit.assert_called_once()
        # Maintenance and snooze cleared
        self.assertFalse(states["S19JPRO-23|192.168.1.23:4028"].is_shutdown_maintenance)
        self.assertIsNone(states["S19JPRO-23|192.168.1.23:4028"].snooze_until_ts)

        # Test pbr:snooze:60
        mock_edit.reset_mock()
        handled_snz = process_post_blackout_callback(
            cb_data="pbr:snooze:60",
            cb_id="cb_2",
            cb_chat_id=123,
            message_id=456,
            miners=self.miners,
            states=states,
            state_lock=self.state_lock,
            state_path="state.json",
            config={},
            bot_token="token",
            answer_cb_fn=mock_ans,
            edit_msg_fn=mock_edit,
            save_state_fn=mock_save,
            tracker=self.tracker,
        )
        self.assertTrue(handled_snz)
        self.assertIsNotNone(states["S19JPRO-23|192.168.1.23:4028"].snooze_until_ts)
        mock_edit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
