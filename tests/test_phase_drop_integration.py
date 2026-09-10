"""Integration tests for Fast Phase Drop vs Connectivity Discriminator (Spec 051).

Validates end-to-end integration with mock telegram dispatch, event_store persistence,
instant hysteresis bypass, cooldown mechanics, and network isolation suppression.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.governance.phase_drop_discriminator import (
    PhaseDropConfig,
    PhaseDropVerdict,
    process_phase_drop_cycle,
)
from app.telegram.help_center import visible_line_width


class MockMinerState:
    def __init__(self, state: str = "OK", offline_streak: int = 0) -> None:
        self.state = state
        self.offline_streak = offline_streak
        self.low_streak = 0
        self.ok_streak = 0
        self.snooze_until_ts = None
        self.is_shutdown_maintenance = False


class TestPhaseDropIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.1.123", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.1.124", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.1.125", "port": 4028, "electrical_group": "elevator_2"},
            {"name": "S19JPRO-26", "host": "192.168.1.126", "port": 4028, "electrical_group": "elevator_2"},
        ]
        self.states = {
            f"{m['name']}|{m['host']}:{m['port']}": MockMinerState()
            for m in self.miners
        }
        self.config = PhaseDropConfig(
            enabled=True,
            cooldown_seconds=300.0,
        )
        self.last_alert_ts: dict[str, float] = {}
        self.active_drops: set[str] = set()

    def test_elevator_drop_bypasses_hysteresis_and_alerts_immediately(self) -> None:
        mock_send_tg = MagicMock()
        mock_record_event = MagicMock()
        mock_log = MagicMock()

        failed = [self.miners[0], self.miners[1]]
        responded = [self.miners[2], self.miners[3]]

        assessment = process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=1000.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            log_fn=mock_log,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: True,
        )

        self.assertEqual(assessment.verdict, PhaseDropVerdict.PHASE_DROP_ELEVATOR)
        self.assertEqual(assessment.affected_groups, ["elevator_1"])

        # Check instant hysteresis bypass
        key_23 = "S19JPRO-23|192.168.1.123:4028"
        key_24 = "S19JPRO-24|192.168.1.124:4028"
        self.assertEqual(self.states[key_23].state, "OFFLINE")
        self.assertEqual(self.states[key_23].offline_streak, 3)
        self.assertEqual(self.states[key_24].state, "OFFLINE")
        self.assertEqual(self.states[key_24].offline_streak, 3)

        # Check Telegram alert dispatched
        mock_send_tg.assert_called_once()
        args, _ = mock_send_tg.call_args
        self.assertEqual(args[0], "test_token")
        self.assertEqual(args[1], "123456")
        card_text = args[2]
        self.assertIn("DISPARO DE CIRCUITO", card_text)
        self.assertIn("elevator_1", card_text)
        self.assertEqual(args[3], "ERROR")
        self.assertEqual(args[4], "phase_drop_phase_drop_elevator")

        # Verify RFC C1 line width limits
        for line in card_text.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

        # Check event_store recording
        mock_record_event.assert_called_once()
        ev_kwargs = mock_record_event.call_args[1]
        self.assertEqual(ev_kwargs["event_type"], "electrical_phase_drop")
        self.assertEqual(ev_kwargs["severity"], "critical")
        self.assertIn("elevator_1", ev_kwargs["miner_name"])

        # Verify tracking state updated
        self.assertEqual(self.last_alert_ts.get("elevator_1"), 1000.0)
        self.assertIn("elevator_1", self.active_drops)

    def test_network_isolation_suppresses_electrical_alert(self) -> None:
        mock_send_tg = MagicMock()
        mock_record_event = MagicMock()
        mock_log = MagicMock()

        failed = list(self.miners)
        responded = []

        assessment = process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=1000.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            log_fn=mock_log,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: False,  # Host gateway unreachable!
        )

        self.assertEqual(assessment.verdict, PhaseDropVerdict.NETWORK_ISOLATION)
        mock_send_tg.assert_not_called()
        mock_record_event.assert_not_called()
        self.assertNotIn("elevator_1", self.active_drops)

    def test_cooldown_prevents_alert_spam(self) -> None:
        mock_send_tg = MagicMock()
        failed = [self.miners[0], self.miners[1]]
        responded = [self.miners[2], self.miners[3]]

        # Cycle 1: Dispatches alert
        process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=1000.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: True,
        )
        self.assertEqual(mock_send_tg.call_count, 1)

        # Cycle 2 at 1030s (30s later, cooldown is 300s): Suppresses alert
        mock_send_tg.reset_mock()
        process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=1030.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: True,
        )
        mock_send_tg.assert_not_called()

        # Cycle 3 at 1305s (> 300s later): Cooldown elapsed, sends alert
        mock_send_tg.reset_mock()
        process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=1305.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: True,
        )
        mock_send_tg.assert_called_once()

    def test_circuit_recovery_clears_active_drops(self) -> None:
        self.active_drops.add("elevator_1")
        mock_log = MagicMock()

        assessment = process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=[],
            tick_responded_miners=self.miners,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=2000.0,
            fails_before_alert=3,
            log_fn=mock_log,
            reachability_fn=lambda **kw: True,
        )

        self.assertEqual(assessment.verdict, PhaseDropVerdict.NORMAL)
        self.assertEqual(len(self.active_drops), 0)
        mock_log.assert_called_once()
        self.assertIn("recovery confirmed", mock_log.call_args[0][0].lower())

    def test_fleet_drop_triggers_fleet_card(self) -> None:
        mock_send_tg = MagicMock()
        mock_record_event = MagicMock()

        failed = list(self.miners)
        responded = []

        assessment = process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=3000.0,
            fails_before_alert=3,
            send_telegram_fn=mock_send_tg,
            record_event_fn=mock_record_event,
            bot_token="test_token",
            chat_id="123456",
            reachability_fn=lambda **kw: True,
        )

        self.assertEqual(assessment.verdict, PhaseDropVerdict.PHASE_DROP_FLEET)
        mock_send_tg.assert_called_once()
        card_text = mock_send_tg.call_args[0][2]
        self.assertIn("CORTE ELÉCTRICO GENERAL", card_text)
        for line in card_text.split("\n"):
            self.assertLessEqual(visible_line_width(line), 32)

        for state in self.states.values():
            self.assertEqual(state.state, "OFFLINE")
            self.assertEqual(state.offline_streak, 3)

    def test_episode_suppression_when_phase_drop_alerts(self) -> None:
        # Verify deduplication: when a phase drop alert occurs, generic opened episodes
        # for those specific miners are suppressed from the episode batch
        failed = [self.miners[0], self.miners[1]]
        responded = [self.miners[2], self.miners[3]]

        assessment = process_phase_drop_cycle(
            miners=self.miners,
            states=self.states,
            tick_failed_miners=failed,
            tick_responded_miners=responded,
            maintenance_miner_ids=set(),
            phase_drop_config=self.config,
            last_alert_ts=self.last_alert_ts,
            active_phase_drops=self.active_drops,
            now_ts=4000.0,
            fails_before_alert=3,
            send_telegram_fn=MagicMock(),
            bot_token="token",
            chat_id="123",
            reachability_fn=lambda **kw: True,
        )

        class MockEpisode:
            def __init__(self, name_display: str, miner_key: str) -> None:
                self.name_display = name_display
                self.miner_key = miner_key

        opened = [
            MockEpisode("S19JPRO-23", "S19JPRO-23|192.168.1.123:4028"),
            MockEpisode("S19JPRO-24", "S19JPRO-24|192.168.1.124:4028"),
            MockEpisode("OTHER-MINER", "OTHER-MINER|192.168.1.200:4028"),
        ]

        aff_set = set(assessment.failed_miners)
        filtered = [
            ep for ep in opened
            if ep.name_display not in aff_set and ep.miner_key not in aff_set
        ]

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].name_display, "OTHER-MINER")


if __name__ == "__main__":
    unittest.main()

