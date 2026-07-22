import unittest
from pathlib import Path
from unittest.mock import patch

from app.miner_monitor import (
    _parse_message_command,
    read_stats_snapshot,
    run_hashcore_cli,
)


class MonitorIncidentMessageTests(unittest.TestCase):
    def test_all_monitor_subprocesses_request_no_window(self) -> None:
        source = Path("app/miner_monitor.py").read_text(encoding="utf-8")

        self.assertGreater(source.count("subprocess.run("), 0)
        self.assertEqual(
            source.count("subprocess.run("),
            source.count("creationflags=_NO_WINDOW_CREATION_FLAGS"),
        )

    def test_qa_guard_blocks_before_hashcore_process(self) -> None:
        with patch("app.miner_monitor.subprocess.run") as process_run:
            ok, message = run_hashcore_cli(
                {"enabled": True, "cli_path": "C:/fake/toolkit_cli.bat"},
                {"name": "S19JPRO-23", "host": "10.0.0.23", "port": 4028},
                "reboot",
                {},
                True,
                False,
            )

        self.assertFalse(ok)
        self.assertIn("bloqueada", message.lower())
        process_run.assert_not_called()

    def test_history_commands_parse_with_group_suffix(self) -> None:
        item = {
            "message": {
                "text": "/events@MinerAlertsBot 23",
                "entities": [
                    {"type": "bot_command", "offset": 0, "length": 22}
                ],
            }
        }

        _, _, command, args, _, _ = _parse_message_command(item)

        self.assertEqual("events", command)
        self.assertEqual(["23"], args)

    def test_event_detail_command_parses_id(self) -> None:
        item = {"message": {"text": "/event 42", "entities": []}}

        _, _, command, args, _, _ = _parse_message_command(item)

        self.assertEqual("event", command)
        self.assertEqual(["42"], args)

    def test_click_safe_event_alias_normalizes_before_dispatch(self) -> None:
        item = {
            "message": {
                "text": "/e37@MinerAlertsBot",
                "entities": [
                    {"type": "bot_command", "offset": 0, "length": 19}
                ],
            }
        }

        _, _, command, args, _, meta = _parse_message_command(item)

        self.assertEqual("event", command)
        self.assertEqual(["37"], args)
        self.assertEqual("event", meta["cmd_normalized"])
        self.assertEqual("event", meta["alias_used"])

    def test_why_command_parses_with_group_suffix(self) -> None:
        item = {
            "message": {
                "text": "/why@MinerAlertsBot 23",
                "entities": [{"type": "bot_command", "offset": 0, "length": 19}],
            }
        }

        _, _, command, args, _, _ = _parse_message_command(item)

        self.assertEqual("why", command)
        self.assertEqual(["23"], args)

    def test_stats_snapshot_reads_vnish_board_signal_after_metadata_entry(self) -> None:
        response = {
            "STATS": [
                {"STATUS": "S"},
                {"chain_acn1": 126, "chain_acn2": 126, "chain_acn3": 126},
            ]
        }
        with patch("app.miner_monitor._read_command", return_value=response):
            active_boards, responded, raw = read_stats_snapshot("h23", 4028)

        self.assertTrue(responded)
        self.assertEqual(3, active_boards)
        self.assertIs(response, raw)


if __name__ == "__main__":
    unittest.main()
