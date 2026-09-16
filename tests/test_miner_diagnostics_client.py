import unittest
from unittest.mock import patch

from tools.miner_diagnostics import read_command


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


if __name__ == "__main__":
    unittest.main()
