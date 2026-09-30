"""Unit tests for Firmware Settings Corruption Watchdog & Assisted Recovery (Spec 080 / PROP-016).

Validates:
1. check_miner_settings_health parsing (duplicate JSON fields, failure_code 1002, clean 200 OK).
2. build_firmware_corruption_keyboard interactive Telegram UI.
3. EventStore recording of firmware_settings_corrupted operational events.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.event_store import EventStore
from app.telegram.fleet_cards import build_firmware_corruption_keyboard
from app.vnish.client import check_miner_settings_health


class TestFirmwareCorruptionWatchdog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_fw_corrupt.db"
        self.store = EventStore(self.db_path)

    def tearDown(self):
        if hasattr(self, "store") and self.store:
            self.store.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @patch("app.vnish.client.get_miner_status")
    def test_detects_failure_code_1002(self, mock_get_status):
        mock_get_status.return_value = (
            True,
            {
                "miner_state": "failure",
                "failure_code": 1002,
                "description": "Failed to parse miner configuration",
            },
            None,
        )
        healthy, issue_code, issue_msg = check_miner_settings_health("192.168.100.24", "admin")
        self.assertFalse(healthy)
        self.assertEqual(issue_code, "config_parse_failure")
        self.assertIn("1002", str(issue_msg))

    @patch("app.vnish.client.get_miner_status")
    @patch("app.vnish.client.unlock_miner")
    @patch("requests.get")
    def test_detects_http_500_duplicate_field(self, mock_requests_get, mock_unlock, mock_get_status):
        mock_get_status.return_value = (
            True,
            {"miner_state": "mining", "miner_state_time": 1000},
            None,
        )
        mock_unlock.return_value = (True, "mock_token", None)
        
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {
            "err": "Could not parse file /config/cgminer.conf duplicate field `fan-fixed-duty` at line 42 column 20"
        }
        mock_requests_get.return_value = mock_resp

        healthy, issue_code, issue_msg = check_miner_settings_health("192.168.100.24", "admin")
        self.assertFalse(healthy)
        self.assertEqual(issue_code, "duplicate_field_error")
        self.assertIn("fan-fixed-duty", str(issue_msg))

    @patch("app.vnish.client.get_miner_status")
    @patch("app.vnish.client.unlock_miner")
    @patch("requests.get")
    def test_healthy_when_settings_return_200(self, mock_requests_get, mock_unlock, mock_get_status):
        mock_get_status.return_value = (
            True,
            {"miner_state": "mining", "miner_state_time": 1000},
            None,
        )
        mock_unlock.return_value = (True, "mock_token", None)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests_get.return_value = mock_resp

        healthy, issue_code, issue_msg = check_miner_settings_health("192.168.100.24", "admin")
        self.assertTrue(healthy)
        self.assertEqual(issue_code, "OK")
        self.assertIsNone(issue_msg)

    def test_firmware_corruption_keyboard(self):
        kb = build_firmware_corruption_keyboard("S19JPRO-24")
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        self.assertGreaterEqual(len(rows), 2)
        
        # Row 0: Reboot confirmation request and diagnostics
        self.assertEqual(rows[0][0]["text"], "⚡ Solicitar Reinicio")
        self.assertEqual(rows[0][0]["callback_data"], "cc:act:rb_req:24")
        self.assertEqual(rows[0][1]["text"], "🔍 Diagnóstico")
        self.assertEqual(rows[0][1]["callback_data"], "diag:ref:diagnose")

        # Row 1: Report & Main Menu
        self.assertEqual(rows[1][0]["text"], "☀️ Reporte")
        self.assertEqual(rows[1][0]["callback_data"], "diag:ref:digest")
        self.assertEqual(rows[1][1]["text"], "📱 Menú")
        self.assertEqual(rows[1][1]["callback_data"], "cc:nav:main")

    def test_event_store_records_firmware_corruption_event(self):
        ev_id = self.store.record_event(
            occurred_ts=1750000000.0,
            miner_key="S19JPRO-24|192.168.100.24:4028",
            miner_name="S19JPRO-24",
            host="192.168.100.24",
            event_type="firmware_settings_corrupted",
            severity="warning",
            summary="Configuración de firmware corrupta (duplicate_field_error): fan-fixed-duty",
            details={"issue_code": "duplicate_field_error"},
        )
        self.assertIsNotNone(ev_id)
        ev = self.store.get_event(ev_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["event_type"], "firmware_settings_corrupted")
        self.assertEqual(ev["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
