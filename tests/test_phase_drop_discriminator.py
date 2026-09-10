"""Unit tests for Fast Phase Drop vs Connectivity Discriminator (Spec 051)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.governance.phase_drop_discriminator import (
    PhaseDropAssessment,
    PhaseDropVerdict,
    check_host_gateway_reachability,
    evaluate_phase_drop,
    render_phase_drop_alert,
)
from app.telegram.help_center import visible_line_width


class TestPhaseDropDiscriminator(unittest.TestCase):
    def setUp(self) -> None:
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.123", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.1.124", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.1.125", "port": 4028, "electrical_group": "elevator_2"},
            {"name": "S19JPRO-26", "host": "192.168.1.126", "port": 4028, "electrical_group": "elevator_2"},
        ]

    def test_verdict_normal(self) -> None:
        assessment = evaluate_phase_drop(
            failed_miners=[],
            responded_miners=self.miners,
            host_network_ok=True,
        )
        self.assertEqual(assessment.verdict, PhaseDropVerdict.NORMAL)
        self.assertEqual(len(assessment.failed_miners), 0)
        self.assertEqual(len(assessment.responded_miners), 4)

    def test_verdict_phase_drop_elevator(self) -> None:
        failed = [self.miners[0], self.miners[1]]  # Both in elevator_1
        responded = [self.miners[2], self.miners[3]]  # Both in elevator_2

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=True,
        )
        self.assertEqual(assessment.verdict, PhaseDropVerdict.PHASE_DROP_ELEVATOR)
        self.assertEqual(assessment.affected_groups, ["elevator_1"])
        self.assertEqual(assessment.active_groups, ["elevator_2"])
        self.assertEqual(len(assessment.failed_miners), 2)
        self.assertIn("S19JPRO-23", assessment.failed_miners)
        self.assertIn("S19JPRO-24", assessment.failed_miners)

    def test_verdict_phase_drop_fleet(self) -> None:
        failed = list(self.miners)
        responded = []

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=True,
        )
        self.assertEqual(assessment.verdict, PhaseDropVerdict.PHASE_DROP_FLEET)
        self.assertEqual(sorted(assessment.affected_groups), ["elevator_1", "elevator_2"])
        self.assertEqual(len(assessment.failed_miners), 4)
        self.assertEqual(len(assessment.responded_miners), 0)

    def test_verdict_network_isolation_suppresses_alert(self) -> None:
        # Whole fleet failed, but host network is down (e.g. host cable disconnected)
        failed = list(self.miners)
        responded = []

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=False,
        )
        self.assertEqual(assessment.verdict, PhaseDropVerdict.NETWORK_ISOLATION)
        self.assertFalse(assessment.host_network_ok)
        self.assertIn("suprimido", assessment.details)

    def test_verdict_individual_failures_no_unison(self) -> None:
        # Only 1 miner fails in elevator_1, the other is OK
        failed = [self.miners[0]]
        responded = [self.miners[1], self.miners[2], self.miners[3]]

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=True,
        )
        self.assertEqual(assessment.verdict, PhaseDropVerdict.INDIVIDUAL_FAILURES)
        self.assertEqual(len(assessment.failed_miners), 1)

    def test_maintenance_exclusion_deliberate_shutdown(self) -> None:
        # Both miners of elevator_1 are in intentional maintenance (/shutdown)
        failed = [self.miners[0], self.miners[1]]
        responded = [self.miners[2], self.miners[3]]
        maint_ids = {"S19JPRO-23", "S19JPRO-24"}

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=True,
            maintenance_miner_ids=maint_ids,
        )
        # Should be NORMAL because all non-maintenance miners are responding
        self.assertEqual(assessment.verdict, PhaseDropVerdict.NORMAL)
        self.assertEqual(len(assessment.failed_miners), 0)

    def test_maintenance_partial_does_not_trigger_unison_drop(self) -> None:
        # 1 miner in maintenance, 1 miner fails. Remaining active in elevator_1 is only 1 miner (< min_group_size=2)
        failed = [self.miners[0], self.miners[1]]
        responded = [self.miners[2], self.miners[3]]
        maint_ids = {"S19JPRO-23"}

        assessment = evaluate_phase_drop(
            failed_miners=failed,
            responded_miners=responded,
            host_network_ok=True,
            maintenance_miner_ids=maint_ids,
        )
        # S19JPRO-24 is the only active failure -> individual failure, not group phase drop
        self.assertEqual(assessment.verdict, PhaseDropVerdict.INDIVIDUAL_FAILURES)
        self.assertEqual(assessment.failed_miners, ["S19JPRO-24"])

    def test_check_host_gateway_reachability_mock_success(self) -> None:
        mock_sock = MagicMock()
        mock_connector = MagicMock(return_value=mock_sock)

        reachable = check_host_gateway_reachability(
            gateway_host="192.168.1.1",
            port=53,
            timeout=0.2,
            socket_fn=mock_connector,
        )
        self.assertTrue(reachable)
        mock_connector.assert_called_once_with(("192.168.1.1", 53), timeout=0.2)
        mock_sock.close.assert_called_once()

    def test_check_host_gateway_reachability_mock_failure(self) -> None:
        mock_connector = MagicMock(side_effect=OSError("Connection refused"))

        reachable = check_host_gateway_reachability(
            gateway_host="10.254.254.254",
            socket_fn=mock_connector,
        )
        self.assertFalse(reachable)

    def test_render_phase_drop_alert_elevator_width_limits(self) -> None:
        failed = [
            {"name": "S19JPRO-23-VERY-LONG-NAME", "host": "192.168.1.123", "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24-EXTRA-LONG-NAME", "host": "192.168.1.124", "electrical_group": "elevator_1"},
        ]
        responded = [self.miners[2], self.miners[3]]
        assessment = evaluate_phase_drop(failed, responded, host_network_ok=True)

        card = render_phase_drop_alert(assessment)
        self.assertIn("DISPARO DE CIRCUITO", card)
        self.assertIn("elevator_1", card)

        for line in card.split("\n"):
            width = visible_line_width(line)
            self.assertLessEqual(
                width,
                32,
                f"Line exceeds 32 visible columns (width={width}): {line!r}",
            )

    def test_render_phase_drop_alert_fleet_width_limits(self) -> None:
        failed = list(self.miners)
        assessment = evaluate_phase_drop(failed, [], host_network_ok=True)

        card = render_phase_drop_alert(assessment)
        self.assertIn("CORTE ELÉCTRICO GENERAL", card)

        for line in card.split("\n"):
            width = visible_line_width(line)
            self.assertLessEqual(
                width,
                32,
                f"Line exceeds 32 visible columns (width={width}): {line!r}",
            )

    def test_render_phase_drop_alert_isolation_width_limits(self) -> None:
        failed = list(self.miners)
        assessment = evaluate_phase_drop(failed, [], host_network_ok=False)

        card = render_phase_drop_alert(assessment)
        self.assertIn("AISLAMIENTO DE RED HOST", card)

        for line in card.split("\n"):
            width = visible_line_width(line)
            self.assertLessEqual(
                width,
                32,
                f"Line exceeds 32 visible columns (width={width}): {line!r}",
            )


if __name__ == "__main__":
    unittest.main()
