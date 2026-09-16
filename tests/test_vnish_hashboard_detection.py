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
        from app.core.engine import DetectionHook, ActuatorHook
        from app.miner_monitor import MinerState

        # 1. Precedencia: placas faltantes tiene prioridad sobre hashrate bajo
        st_hashboard = DetectionHook.classify_state(
            responded=True,
            rate_ths=20.0,
            threshold_ths=60.0,
            active_boards=2,
            expected_boards=3,
        )
        self.assertEqual("HASHBOARD", st_hashboard)

        st_low = DetectionHook.classify_state(
            responded=True,
            rate_ths=20.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
        )
        self.assertEqual("LOW", st_low)

        # 2. Política de auto-reboot: HASHBOARD no se evalúa con timer de LOW
        st = MinerState(state="HASHBOARD", low_since_ts=None, hashboard_since_ts=1000.0)
        res = ActuatorHook.evaluate_auto_reboot_policy(
            state=st,
            miner={"name": "M1"},
            new_state="HASHBOARD",
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            now_ts=2000.0,
            hashboard_sustained_seconds=600,
        )
        self.assertTrue(res["allowed"])


if __name__ == "__main__":
    unittest.main()
