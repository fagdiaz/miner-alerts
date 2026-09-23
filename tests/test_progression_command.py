"""
Unit tests for Power Progression Telegram Command (/progression) - Spec 079 / PROP-014.
"""

from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock

from app.telegram.context import TelegramRequestContext
from app.telegram.commands.progression import ProgressionCommand
from app.governance.power_progression import (
    PROFILE_C0_BASE_STABLE,
    PROFILE_C1_ASYMMETRIC,
    PROFILE_C4_MAX_POWER,
    get_global_progression_state,
    set_global_desired_profile,
)


class TestProgressionCommand(unittest.TestCase):
    def setUp(self):
        self.sent_messages = []

        def mock_send(text, **kwargs):
            self.sent_messages.append((text, kwargs))
            return True

        self.mock_send = mock_send

        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2", "max_hardware_preset": "2500W"},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
        ]

        class DummyState:
            def __init__(self, temp, duty, pwr, preset):
                self.last_max_chip_temp = temp
                self.last_fan_duty_percent = duty
                self.last_power_w = pwr
                self.balancer_preset = preset

        self.states = {
            "S19JPRO-23|192.168.100.23:4028": DummyState(81.0, 96.0, 2499.0, "2500W"),
            "S19JPRO-24|192.168.100.24:4028": DummyState(82.0, 100.0, 2498.0, "2500W"),
            "S19JPRO-25|192.168.100.25:4028": DummyState(81.0, 92.0, 2499.0, "2500W"),
            "S19JPRO-26|192.168.100.26:4028": DummyState(81.0, 92.0, 2699.0, "2700W"),
        }
        self.lock = threading.Lock()
        self.config = {
            "valley_step_up_max_chip_temp_c": 80.0,
            "valley_step_up_max_fan_duty_pct": 90.0,
        }

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

        # Reset global state for testing
        st = get_global_progression_state()
        st.desired_profile = PROFILE_C4_MAX_POWER
        st.current_profile = PROFILE_C1_ASYMMETRIC
        st.last_transition_ts = 0.0

    def test_progression_dashboard_view(self):
        cmd = ProgressionCommand()
        res = cmd.handle(self.context, args=[], from_id=123456)
        self.assertTrue(res)
        self.assertEqual(len(self.sent_messages), 1)
        text, _ = self.sent_messages[0]
        self.assertIn("POWER PROGRESSION ORCHESTRATOR", text)
        self.assertIn("Perfil Activo: *C1_ASYMMETRIC*", text)
        self.assertIn("ELEVADOR 1", text)
        self.assertIn("ELEVADOR 2", text)
        self.assertIn("S19JPRO-23", text)
        self.assertIn("S19JPRO-26", text)

    def test_progression_set_valid_profile_c4(self):
        cmd = ProgressionCommand()
        res = cmd.handle(self.context, args=["c4"], from_id=123456)
        self.assertTrue(res)
        st = get_global_progression_state()
        self.assertEqual(st.desired_profile, PROFILE_C4_MAX_POWER)
        text, _ = self.sent_messages[0]
        self.assertIn("PERFIL OBJETIVO ACTUALIZADO", text)
        self.assertIn("C4_MAX_POWER", text)

    def test_progression_set_valid_profile_c0(self):
        cmd = ProgressionCommand()
        res = cmd.handle(self.context, args=["c0"], from_id=123456)
        self.assertTrue(res)
        st = get_global_progression_state()
        self.assertEqual(st.desired_profile, PROFILE_C0_BASE_STABLE)
        text, _ = self.sent_messages[0]
        self.assertIn("PERFIL OBJETIVO ACTUALIZADO", text)
        self.assertIn("C0_BASE_STABLE", text)

    def test_progression_set_invalid_profile(self):
        cmd = ProgressionCommand()
        res = cmd.handle(self.context, args=["super_turbo_unknown"], from_id=123456)
        self.assertTrue(res)
        text, _ = self.sent_messages[0]
        self.assertIn("Perfil desconocido", text)

    def test_progression_explains_hold_reason_in_dashboard(self):
        cmd = ProgressionCommand()
        res = cmd.handle(self.context, args=[], from_id=123456)
        self.assertTrue(res)
        text, _ = self.sent_messages[0]
        # Should explain why candidate S19JPRO-23 cannot be promoted (chip >= 80C or fans >= 90%)
        self.assertIn("ESTADO DEL ORQUESTADOR", text)
        self.assertIn("Acción:", text)


if __name__ == "__main__":
    unittest.main()
