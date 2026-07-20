import unittest
from unittest.mock import patch

from app.miner_monitor import (
    _parse_message_command,
    format_restart_incident,
    read_stats_snapshot,
    run_hashcore_cli,
)
from app.restart_intelligence import RestartClassification


class MonitorIncidentMessageTests(unittest.TestCase):
    def test_unexpected_restart_message_has_actionable_evidence(self) -> None:
        classification = RestartClassification(
            classification="unexpected",
            severity="critical",
            restart_reason="elapsed_reset",
            action_source=None,
            action_ts=None,
            action_age_seconds=None,
        )

        message = format_restart_incident(
            event_id=42,
            name_display="23",
            previous_elapsed=86_400,
            current_elapsed=120,
            classification=classification,
            state="OK",
            rate_ths=99.2,
            attribution_window_seconds=900,
        )

        self.assertIn("REINICIO NO ESPERADO", message)
        self.assertIn("86400s -> 120s", message)
        self.assertIn("ninguna en los ultimos 15 min", message)
        self.assertIn("Detalle: /event 42", message)

    def test_expected_restart_message_names_related_action(self) -> None:
        classification = RestartClassification(
            classification="expected_manual",
            severity="info",
            restart_reason="elapsed_drop",
            action_source="manual",
            action_ts=9_900.0,
            action_age_seconds=100.0,
        )

        message = format_restart_incident(
            event_id=7,
            name_display="24",
            previous_elapsed=20_000,
            current_elapsed=80,
            classification=classification,
            state="LOW",
            rate_ths=15.0,
            attribution_window_seconds=900,
        )

        self.assertIn("REINICIO DETECTADO", message)
        self.assertIn("manual hace 100s", message)

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

    def test_stats_snapshot_preserves_existing_first_entry_board_signal(self) -> None:
        response = {
            "STATS": [
                {"STATUS": "S"},
                {"chain_acn": [63, 63, 63], "chain_vol1": 12825},
            ]
        }
        with patch("app.miner_monitor._read_command", return_value=response):
            active_boards, responded, raw = read_stats_snapshot("h23", 4028)

        self.assertTrue(responded)
        self.assertIsNone(active_boards)
        self.assertIs(response, raw)


if __name__ == "__main__":
    unittest.main()
