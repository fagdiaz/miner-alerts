"""Integration tests for Scheduled Maintenance Windows & Soft Pre-Ramp (Spec 052).

Simulates end-to-end timeline: scheduling -> T-10m pre-ramp -> T-5m pre-ramp -> T-0 safe shutdown
with active thermal purge -> state persistence and cancellation.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.governance.maintenance_scheduler import (
    ScheduledStage,
    ScheduledWindow,
    parse_schedule_expression,
    process_maintenance_scheduler_cycle,
    render_schedule_cancelled_card,
)
from app.telegram.help_center import visible_line_width


class MockMinerState:
    def __init__(self) -> None:
        self.state = "OK"
        self.is_shutdown_maintenance = False
        self.snooze_until_ts = None


class TestMaintenanceSchedulerIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.123", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.1.124", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.1.125", "port": 4028},
            {"name": "S19JPRO-26", "host": "192.168.1.126", "port": 4028},
        ]
        self.states = {
            f"{m['name']}|{m['host']}:{m['port']}": MockMinerState()
            for m in self.miners
        }
        self.config = {
            "vnish_api_password": "test_password",
            "fan_governor_emergency_temp_c": 83.5,
        }

    def test_full_timeline_execution(self) -> None:
        mock_send_tg = MagicMock()
        mock_record_event = MagicMock()
        mock_preset = MagicMock()
        mock_shutdown = MagicMock(return_value={})
        mock_fan = MagicMock()
        mock_save = MagicMock()

        # Start at t=1000. Schedule for in 30m (t=2800) with 2h (7200s) duration
        ok, window, _ = parse_schedule_expression("in 30m", "2h", now_ts=1000.0)
        self.assertTrue(ok)
        assert window is not None
        self.assertEqual(window.start_ts, 2800.0)
        self.assertEqual(window.end_ts, 2800.0 + 7200.0)

        # 1. Tick at t=1500 (T-1300s, before T-10m) -> Stage stays PENDING
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=1500.0,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            preset_fn=mock_preset,
            shutdown_fn=mock_shutdown,
            fan_fn=mock_fan,
            bot_token="tok",
            chat_id="123",
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.PENDING)
        mock_preset.assert_not_called()
        mock_shutdown.assert_not_called()

        # 2. Tick at t=2200 (T-600s = T-10m) -> Triggers Pre-Ramp Tier 1 (2300W)
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=2200.0,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            preset_fn=mock_preset,
            shutdown_fn=mock_shutdown,
            fan_fn=mock_fan,
            bot_token="tok",
            chat_id="123",
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.PRE_RAMP_TIER_1)
        self.assertEqual(mock_preset.call_count, 4)  # All 4 miners set to 2300W
        mock_preset.assert_any_call("192.168.1.123", "test_password", "2300W", timeout=2.5)
        self.assertEqual(mock_send_tg.call_count, 1)
        self.assertIn("PRE-RAMPA", mock_send_tg.call_args[0][2])
        self.assertIn("2300W", mock_send_tg.call_args[0][2])

        # 3. Tick at t=2500 (T-300s = T-5m) -> Triggers Pre-Ramp Tier 2 (2100W)
        mock_preset.reset_mock()
        mock_send_tg.reset_mock()
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=2500.0,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            preset_fn=mock_preset,
            shutdown_fn=mock_shutdown,
            fan_fn=mock_fan,
            bot_token="tok",
            chat_id="123",
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.PRE_RAMP_TIER_2)
        self.assertEqual(mock_preset.call_count, 4)  # All 4 miners set to 2100W
        mock_preset.assert_any_call("192.168.1.123", "test_password", "2100W", timeout=2.5)
        self.assertEqual(mock_send_tg.call_count, 1)
        self.assertIn("2100W", mock_send_tg.call_args[0][2])

        # 4. Tick at t=2800 (T-0) -> Triggers Safe Shutdown + Thermal Purge + Snooze
        mock_send_tg.reset_mock()
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=2800.0,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            preset_fn=mock_preset,
            shutdown_fn=mock_shutdown,
            fan_fn=mock_fan,
            bot_token="tok",
            chat_id="123",
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.EXECUTED)
        mock_shutdown.assert_called_once()
        mock_fan.assert_called_once()

        # Check all states updated to maintenance & snooze
        for st in self.states.values():
            self.assertTrue(st.is_shutdown_maintenance)
            self.assertEqual(st.snooze_until_ts, 2800.0 + 7200.0)

        # Check safe area telegram card sent
        mock_send_tg.assert_called_once()
        card_text = mock_send_tg.call_args[0][2]
        self.assertIn("ÁREA ELÉCTRICA SEGURA", card_text)
        for line in card_text.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

        # 5. Tick at t=10005 (> end_ts = 10000) -> Completes window
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=10005.0,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            preset_fn=mock_preset,
            shutdown_fn=mock_shutdown,
            fan_fn=mock_fan,
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.COMPLETED)

    def test_cancellation_flow(self) -> None:
        ok, window, _ = parse_schedule_expression("in 30m", "2h", now_ts=1000.0)
        self.assertTrue(ok)
        assert window is not None

        # Cancel window
        window.stage = ScheduledStage.CANCELLED
        cancelled_card = render_schedule_cancelled_card()
        self.assertIn("VENTANA CANCELADA", cancelled_card)

        # Run cycle at T-10m -> should do nothing because stage is CANCELLED
        mock_preset = MagicMock()
        window = process_maintenance_scheduler_cycle(
            window=window,
            miners=self.miners,
            states=self.states,
            config=self.config,
            now_ts=2200.0,
            preset_fn=mock_preset,
        )
        assert window is not None
        self.assertEqual(window.stage, ScheduledStage.CANCELLED)
        mock_preset.assert_not_called()

    def test_persistence_reconstitution(self) -> None:
        ok, original, _ = parse_schedule_expression("in 1h", "3h", now_ts=5000.0, user_id="operador_1")
        self.assertTrue(ok)
        assert original is not None
        original.stage = ScheduledStage.PRE_RAMP_TIER_1

        # Simulate save to state.json
        state_payload = {"scheduled_maintenance": original.to_dict()}

        # Simulate restart & load_state
        restored = ScheduledWindow.from_dict(state_payload["scheduled_maintenance"])
        self.assertEqual(restored.window_id, original.window_id)
        self.assertEqual(restored.start_ts, original.start_ts)
        self.assertEqual(restored.duration_seconds, original.duration_seconds)
        self.assertEqual(restored.stage, ScheduledStage.PRE_RAMP_TIER_1)
        self.assertEqual(restored.created_by, "operador_1")


if __name__ == "__main__":
    unittest.main()
