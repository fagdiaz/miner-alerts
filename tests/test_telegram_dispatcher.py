"""Unit and Integration Tests for Decoupled Telegram Dispatcher (Spec 058)."""

from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.telegram.context import TelegramRequestContext
from app.telegram.commands.base import BaseCommandHandler
from app.telegram.router import (
    TelegramCommandRouter,
    TelegramCallbackRouter,
    create_default_command_router,
)


class DummySuccessCommand(BaseCommandHandler):
    name = "dummy"
    aliases = ["d", "tonto"]
    description = "Test dummy command"

    def handle(self, context, args, update_id=None, from_id=None, message_id=None, cmd_name="", **kwargs) -> bool:
        context.send_message(f"DUMMY_OK args={args} cmd={cmd_name}")
        return True


class DummyFailingCommand(BaseCommandHandler):
    name = "fail"
    aliases = ["error"]
    description = "Test failing command"

    def handle(self, context, args, update_id=None, from_id=None, message_id=None, cmd_name="", **kwargs) -> bool:
        raise ValueError("Simulated handler crash")


class TelegramDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_lock = threading.Lock()
        self.state_path = Path("test_state.json")
        self.states = {}
        self.context = TelegramRequestContext(
            bot_token="TEST_TOKEN",
            chat_id="123456",
            config={"telegram": {"chat_id": 123456}},
            miners=[{"name": "23", "host": "192.168.100.23", "port": 4028}],
            states=self.states,
            state_lock=self.state_lock,
            state_path=self.state_path,
        )

    def test_router_registration_and_alias_resolution(self) -> None:
        router = TelegramCommandRouter()
        handler = DummySuccessCommand()
        router.register(handler)

        # Match by canonical name
        self.assertIs(router.find_handler("dummy"), handler)
        self.assertIs(router.find_handler("/dummy"), handler)
        self.assertIs(router.find_handler("/dummy@MyBot"), handler)

        # Match by aliases
        self.assertIs(router.find_handler("d"), handler)
        self.assertIs(router.find_handler("/d"), handler)
        self.assertIs(router.find_handler("tonto"), handler)

        # Unregistered command
        self.assertIsNone(router.find_handler("unknown_command"))

    def test_authorization_rejection(self) -> None:
        router = TelegramCommandRouter()
        router.register(DummySuccessCommand())

        with patch.object(self.context, "send_message") as mock_send:
            # Unauthorized sender (from_id != context.chat_id)
            handled = router.dispatch(
                cmd_name="dummy",
                args=["test"],
                context=self.context,
                update_id=1,
                from_id=999999,  # Unauthorized
            )
            self.assertTrue(handled)
            mock_send.assert_not_called()

    def test_dispatch_execution_success(self) -> None:
        router = TelegramCommandRouter()
        router.register(DummySuccessCommand())

        with patch.object(self.context, "send_message") as mock_send:
            handled = router.dispatch(
                cmd_name="dummy",
                args=["arg1", "arg2"],
                context=self.context,
                update_id=1,
                from_id=123456,  # Authorized
            )
            self.assertTrue(handled)
            mock_send.assert_called_once()
            call_text = mock_send.call_args[0][0]
            self.assertIn("DUMMY_OK", call_text)
            self.assertIn("arg1", call_text)

    def test_error_boundary_and_no_silence_guarantee(self) -> None:
        router = TelegramCommandRouter()
        router.register(DummyFailingCommand())

        with patch.object(self.context, "send_message") as mock_send:
            handled = router.dispatch(
                cmd_name="fail",
                args=[],
                context=self.context,
                update_id=2,
                from_id=123456,
            )
            self.assertTrue(handled)
            # Must notify operator instead of crashing worker
            mock_send.assert_called_once()
            call_text = mock_send.call_args[0][0]
            self.assertIn("Error ejecutando /fail", call_text)
            self.assertIn("Simulated handler crash", call_text)
            self.assertEqual(mock_send.call_args[1].get("msg_type"), "ERROR")

    def test_default_production_router_covers_fleet_commands(self) -> None:
        router = create_default_command_router()
        canonical_commands = [
            "status",
            "info",
            "fans",
            "silent",
            "governor",
            "interventions",
            "contingency",
            "balancer",
            "elevadores",
            "reboot",
            "reboot_no_ok",
            "confirm",
            "diagnose",
            "firmware",
            "quality",
            "health",
            "chart",
            "events",
            "event",
            "why",
            "chains",
            "efficiency",
            "presets",
            "selftest",
            "snooze",
            "unsnooze",
            "snoozed",
            "shutdown",
            "resume",
            "schedule_maintenance",
            "scheduled",
            "help",
            "menu",
            "digest",
        ]
        for cmd in canonical_commands:
            handler = router.find_handler(cmd)
            self.assertIsNotNone(handler, f"Command /{cmd} must be registered in production router")

    def test_spanish_aliases_resolved_correctly(self) -> None:
        router = create_default_command_router()
        spanish_checks = [
            ("estado", "status"),
            ("resumen", "status"),
            ("silencio", "silent"),
            ("intervenciones", "interventions"),
            ("contingencia", "contingency"),
            ("reiniciar", "reboot"),
            ("diagnostico", "diagnose"),
            ("salud", "health"),
            ("calidad", "quality"),
            ("grafico", "chart"),
            ("eventos", "events"),
            ("placas", "chains"),
            ("silenciar", "snooze"),
            ("desilenciar", "unsnooze"),
            ("parada", "shutdown"),
            ("reanudar", "resume"),
            ("programar", "schedule_maintenance"),
            ("ayuda", "help"),
            ("panel", "menu"),
        ]
        for alias, canonical in spanish_checks:
            handler = router.find_handler(alias)
            self.assertIsNotNone(handler, f"Alias /{alias} must map to a handler")
            self.assertEqual(
                handler.name,
                canonical,
                f"Alias /{alias} expected to map to canonical '{canonical}', got '{handler.name}'",
            )

    def test_quick_confirm_shortcut_matching(self) -> None:
        router = create_default_command_router()
        confirm_handler = router.find_handler("confirm")
        self.assertIsNotNone(confirm_handler)

        # /c123456 shortcut matching
        self.assertTrue(confirm_handler.matches("c123456"))
        self.assertTrue(confirm_handler.matches("/c987654"))
        self.assertIs(router.find_handler("c123456"), confirm_handler)

    def test_anti_deadlock_state_persistence(self) -> None:
        with patch("app.miner_monitor._build_state_payload") as mock_build, \
             patch("app.miner_monitor._flush_state_payload") as mock_flush:
            mock_build.return_value = {"states": {}}
            self.context.persist_state_safely()
            mock_build.assert_called_once()
            mock_flush.assert_called_once()


if __name__ == "__main__":
    unittest.main()
