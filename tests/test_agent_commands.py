"""
Unit tests for Facility Governance Agent (FGA) Telegram commands - Spec 079.
"""

import threading
import unittest
from unittest.mock import MagicMock

from app.telegram.context import TelegramRequestContext
from app.telegram.commands.agent import AgentCommand, StrategyCommand, AgentWhyCommand
from app.governance.facility_agent import STRATEGY_BALANCED, STRATEGY_MAX_POWER


class TestAgentCommands(unittest.TestCase):
    def setUp(self):
        self.sent_messages = []

        def mock_send(text, **kwargs):
            self.sent_messages.append((text, kwargs))
            return True

        self.mock_send = mock_send

        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
        ]

        class DummyState:
            def __init__(self, temp, pwr, preset, rate):
                self.governor_last_temp_c = temp
                self.last_temp_c = temp
                self.inlet_temp_c = 25.0
                self.governor_last_power_w = pwr
                self.balancer_preset = preset
                self.rate_ths = rate

        self.states = {
            "S19JPRO-23|192.168.100.23:4028": DummyState(85.0, 2500.0, "2500W", 94.0),
            "S19JPRO-25|192.168.100.25:4028": DummyState(77.0, 2500.0, "2500W", 94.0),
        }
        self.lock = threading.Lock()
        self.config = {"facility_agent_strategy": STRATEGY_BALANCED}

        from pathlib import Path

        self.context = TelegramRequestContext(
            bot_token="test_token",
            chat_id="123456",
            config=self.config,
            miners=self.miners,
            states=self.states,
            state_lock=self.lock,
            state_path=Path("test_state.json"),
        )
        self.context.send_message = self.mock_send

    def test_agent_command_dashboard(self):
        cmd = AgentCommand()
        res = cmd.handle(self.context, args=[], from_id=123456)
        self.assertTrue(res)
        self.assertEqual(len(self.sent_messages), 1)
        text, _ = self.sent_messages[0]
        self.assertIn("FACILITY GOVERNANCE AGENT", text)
        self.assertIn("Estrategia Activa: *BALANCED*", text)
        self.assertIn("S19JPRO-23", text)
        self.assertIn("S19JPRO-25", text)

    def test_strategy_command_query(self):
        cmd = StrategyCommand()
        res = cmd.handle(self.context, args=[], from_id=123456)
        self.assertTrue(res)
        text, _ = self.sent_messages[0]
        self.assertIn("ESTRATEGIA FGA ACTUAL", text)
        self.assertIn("BALANCED", text)

    def test_strategy_command_update(self):
        cmd = StrategyCommand()
        res = cmd.handle(self.context, args=["max_power"], from_id=123456)
        self.assertTrue(res)
        self.assertEqual(self.config.get("facility_agent_strategy"), STRATEGY_MAX_POWER)
        text, _ = self.sent_messages[0]
        self.assertIn("ESTRATEGIA ACTUALIZADA", text)
        self.assertIn("MAX_POWER", text)

    def test_strategy_command_invalid(self):
        cmd = StrategyCommand()
        res = cmd.handle(self.context, args=["turbo_invalid"], from_id=123456)
        self.assertTrue(res)
        text, _ = self.sent_messages[0]
        self.assertIn("Estrategia desconocida", text)

    def test_agent_why_command(self):
        cmd = AgentWhyCommand()
        res = cmd.handle(self.context, args=["23"], from_id=123456)
        self.assertTrue(res)
        text, _ = self.sent_messages[0]
        self.assertIn("Diagnóstico FGA para S19JPRO-23", text)
        self.assertIn("Resistencia Térmica", text)


if __name__ == "__main__":
    unittest.main()
