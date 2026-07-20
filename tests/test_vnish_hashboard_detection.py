import inspect
import unittest
from unittest.mock import patch

from app.miner_monitor import _count_active_boards, main, read_stats_snapshot


class VnishHashboardDetectionTests(unittest.TestCase):
    def test_counts_current_vnish_chain_acn_fields(self) -> None:
        entry = {
            "chain_acn1": 126,
            "chain_acn2": "126",
            "chain_acn3": 126.0,
        }

        self.assertEqual(3, _count_active_boards(entry))

    def test_zero_and_malformed_chain_values_are_not_active(self) -> None:
        entry = {
            "chain_acn1": 126,
            "chain_acn2": 0,
            "chain_acn3": "bad",
        }

        self.assertEqual(1, _count_active_boards(entry))

    def test_unknown_payload_remains_unknown(self) -> None:
        self.assertIsNone(_count_active_boards({"STATUS": "S"}))

    def test_preserves_list_and_legacy_formats(self) -> None:
        self.assertEqual(2, _count_active_boards({"chain_acn": [63, 0, 63]}))
        self.assertEqual(
            2,
            _count_active_boards(
                {
                    "chain0_asicnum": 63,
                    "chain1_alive": 1,
                    "chain2_status": "dead",
                }
            ),
        )

    def test_snapshot_uses_first_stats_entry_with_explicit_board_signal(self) -> None:
        response = {
            "STATS": [
                {"STATUS": "S"},
                {"chain_acn1": 126, "chain_acn2": 126, "chain_acn3": 0},
                {"chain_acn1": 126, "chain_acn2": 126, "chain_acn3": 126},
            ]
        }
        with patch("app.miner_monitor._read_command", return_value=response):
            active_boards, responded, raw = read_stats_snapshot("h23", 4028)

        self.assertTrue(responded)
        self.assertEqual(2, active_boards)
        self.assertIs(response, raw)

    def test_hashboard_precedence_stays_before_low_and_auto_reboot(self) -> None:
        source = inspect.getsource(main)
        state_block = source.split("prev_state = state.state", 1)[1].split("state.state = new_state", 1)[0]
        self.assertLess(
            state_block.index("active_boards < expected_boards"),
            state_block.index("rate_ths < threshold_ths"),
        )
        policy = source.split("# Auto-reboot policy", 1)[1]
        self.assertIn("if new_state == STATE_LOW and state.low_since_ts", policy)
        self.assertNotIn("if new_state == STATE_HASHBOARD and state.low_since_ts", policy)


if __name__ == "__main__":
    unittest.main()
