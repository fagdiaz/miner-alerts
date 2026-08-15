"""Phase 7 — Controlled Telegram Command & Simulation Suite.

Tests Telegram command handlers (/help, /status, /info, /e<ID>) deterministically
without network, external hardware, or reboot actions.
"""

import unittest
from unittest.mock import Mock, patch

from app import miner_monitor
from app.alert_episodes import format_current_status_line
from app.telegram_messages import classify_delivery, split_telegram_message


class ControlledTelegramCommandTests(unittest.TestCase):
    """Fase 7: Controlled validation of Telegram commands and rendering."""

    def test_help_command_renders_cleanly(self) -> None:
        help_index = miner_monitor.render_help_index()
        self.assertIn("MINER ALERTS - AYUDA", help_index)
        self.assertIn("/status", help_index)
        self.assertIn("/help", help_index)

    def test_status_line_rendering_for_all_states(self) -> None:
        # Healthy miner
        ok_line = format_current_status_line(
            name_display="24",
            host="192.168.100.24",
            confirmed_state="OK",
            responded=True,
            rate_ths=98.5,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
        )
        self.assertIn("24", ok_line)
        self.assertIn("98.50 TH/s", ok_line)
        self.assertNotIn("LOW", ok_line)
        self.assertNotIn("OFFLINE", ok_line)

        # Offline miner
        off_line = format_current_status_line(
            name_display="25",
            host="192.168.100.25",
            confirmed_state="OFFLINE",
            responded=False,
            rate_ths=None,
            threshold_ths=60.0,
            active_boards=None,
            expected_boards=3,
            detail_event_id=123,
        )
        self.assertIn("25", off_line)
        self.assertIn("OFFLINE", off_line)
        self.assertIn("/e123", off_line)
        self.assertNotIn("98.50", off_line)

        # Low hash miner
        low_line = format_current_status_line(
            name_display="26",
            host="192.168.100.26",
            confirmed_state="LOW",
            responded=True,
            rate_ths=42.3,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
            detail_event_id=124,
        )
        self.assertIn("26", low_line)
        self.assertIn("42.30 TH/s", low_line)
        self.assertIn("LOW", low_line)
        self.assertIn("/e124", low_line)

    def test_event_alias_normalization(self) -> None:
        """/e123 normalize to cmd_name='event', args=['123']."""
        dummy_msg = {
            "message": {
                "text": "/e123",
                "entities": [{"type": "bot_command", "offset": 0, "length": 5}],
                "from": {"id": 100},
            },
            "update_id": 1,
        }
        parsed = miner_monitor._parse_message_command(dummy_msg)
        self.assertIsNotNone(parsed)
        msg_obj, text, cmd_name, args, msg_key, meta = parsed
        self.assertEqual("event", cmd_name)
        self.assertEqual(["123"], args)
        self.assertEqual("event", meta.get("alias_used"))

    def test_command_delivery_classification_is_command_priority(self) -> None:
        delivery_type = classify_delivery("STATUS", is_command=True)
        self.assertEqual("command", delivery_type)

    def test_large_event_detail_message_splits_safely(self) -> None:
        large_text = "EVENT DETAIL REPLAY\n" + ("Line " * 200 + "\n") * 30
        parts = split_telegram_message(large_text)
        self.assertGreaterEqual(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 3900)


if __name__ == "__main__":
    unittest.main()
