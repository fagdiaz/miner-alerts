import io
import sys
import unittest
from unittest.mock import patch

from tools.miner_diagnostics import read_command
import tools.debug_4028 as debug_4028


class TestMinerDiagnosticsClient(unittest.TestCase):
    @patch("tools.miner_diagnostics.query_cgminer")
    def test_read_command_success(self, mock_query):
        mock_query.return_value = {"STATUS": [{"STATUS": "S"}], "SUMMARY": [{"GHS 5s": 95000.0}]}
        parsed, err = read_command("192.168.1.100", 4028, "summary", timeout=2.0)
        self.assertIsNone(err)
        self.assertIsNotNone(parsed)
        self.assertIn("SUMMARY", parsed)
        mock_query.assert_called_once_with(host="192.168.1.100", port=4028, command="summary", timeout=2.0)

    @patch("tools.miner_diagnostics.query_cgminer")
    def test_read_command_failure(self, mock_query):
        mock_query.return_value = None
        parsed, err = read_command("192.168.1.100", 4028, "summary", timeout=2.0)
        self.assertIsNone(parsed)
        self.assertEqual(err, "empty or failed response")

    @patch("tools.miner_diagnostics.query_cgminer")
    def test_read_command_exception(self, mock_query):
        mock_query.side_effect = ConnectionRefusedError("Connection refused")
        parsed, err = read_command("192.168.1.100", 4028, "summary", timeout=1.0)
        self.assertIsNone(parsed)
        self.assertIn("ConnectionRefusedError", err)


class TestDebug4028Client(unittest.TestCase):
    def test_debug_4028_imports_cgminer_client(self):
        from app.network.cgminer_client import query_cgminer
        self.assertEqual(debug_4028.query_cgminer, query_cgminer)

    @patch("tools.debug_4028.query_cgminer")
    def test_debug_miner_success(self, mock_query):
        mock_query.return_value = {"STATUS": [{"STATUS": "S"}], "SUMMARY": [{"GHS 5s": 98000.0}]}
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = debug_4028.debug_miner("192.168.1.200", 4028, timeout=3.0)
        self.assertEqual(code, 0)
        mock_query.assert_called_once_with("192.168.1.200", 4028, command="summary", timeout=3.0)
        self.assertIn("BYTES:", captured.getvalue())

    @patch("tools.debug_4028.query_cgminer")
    def test_debug_miner_failure(self, mock_query):
        mock_query.return_value = None
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = debug_4028.debug_miner("192.168.1.200", 4028, timeout=3.0)
        self.assertEqual(code, 1)
        self.assertIn("ERROR:", captured.getvalue())

    def test_debug_main_help(self):
        captured = io.StringIO()
        with patch.object(sys, "argv", ["debug_4028.py", "--help"]):
            with patch("sys.stdout", captured):
                code = debug_4028.main()
        self.assertEqual(code, 0)
        self.assertIn("Uso: python tools\\debug_4028.py", captured.getvalue())

    @patch("tools.debug_4028.debug_miner")
    def test_debug_main_delegates_to_debug_miner(self, mock_debug):
        mock_debug.return_value = 0
        with patch.object(sys, "argv", ["debug_4028.py", "192.168.1.55"]):
            code = debug_4028.main()
        self.assertEqual(code, 0)
        mock_debug.assert_called_once_with("192.168.1.55", 4028)


if __name__ == "__main__":
    unittest.main()
