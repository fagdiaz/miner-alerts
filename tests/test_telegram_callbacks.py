"""Unit tests for Telegram interactive callbacks and inline keyboards (Spec 031)."""

from __future__ import annotations

import unittest
import time
from app.telegram.callbacks import (
    CallbackAction,
    CallbackTokenRegistry,
    parse_callback_data,
    build_callback_data,
    build_alert_keyboard,
    build_confirmation_keyboard,
    build_settled_keyboard,
)


class TestTelegramCallbacks(unittest.TestCase):
    def setUp(self):
        self.registry = CallbackTokenRegistry(ttl_seconds=60.0, max_tokens=5)

    def test_parse_valid_callback_data(self):
        action = parse_callback_data("diag:23")
        self.assertEqual(action.action_type, "diag")
        self.assertEqual(action.miner_id, "23")
        self.assertIsNone(action.token)
        self.assertIsNone(action.param)

        action = parse_callback_data("chart:24")
        self.assertEqual(action.action_type, "chart")
        self.assertEqual(action.miner_id, "24")

        action = parse_callback_data("snz:25:60")
        self.assertEqual(action.action_type, "snz")
        self.assertEqual(action.miner_id, "25")
        self.assertEqual(action.param, "60")

        action = parse_callback_data("rb_req:26")
        self.assertEqual(action.action_type, "rb_req")
        self.assertEqual(action.miner_id, "26")

        action = parse_callback_data("rb_cfm:tok123:23")
        self.assertEqual(action.action_type, "rb_cfm")
        self.assertEqual(action.token, "tok123")
        self.assertEqual(action.miner_id, "23")

        action = parse_callback_data("rb_ccl:23")
        self.assertEqual(action.action_type, "rb_ccl")
        self.assertEqual(action.miner_id, "23")

        action = parse_callback_data("noop")
        self.assertEqual(action.action_type, "noop")

    def test_parse_invalid_or_malformed_callback_data(self):
        action = parse_callback_data("")
        self.assertIsNone(action)

        action = parse_callback_data("unknown:action:foo:bar:extra")
        self.assertIsNone(action)

    def test_callback_data_byte_length_constraint(self):
        # Telegram Bot API hard limit is 64 bytes
        samples = [
            build_callback_data("diag", "S19JPRO-23"),
            build_callback_data("chart", "S19JPRO-23"),
            build_callback_data("snz", "S19JPRO-23", param="120"),
            build_callback_data("rb_req", "S19JPRO-23"),
            build_callback_data("rb_cfm", "S19JPRO-23", token="a1b2c3d4"),
            build_callback_data("rb_ccl", "S19JPRO-23"),
            build_callback_data("noop", ""),
        ]
        for s in samples:
            encoded_len = len(s.encode("utf-8"))
            self.assertLessEqual(encoded_len, 64, f"Payload '{s}' exceeds 64 bytes limit ({encoded_len} bytes)")

    def test_token_registry_create_and_consume(self):
        token = self.registry.create_token(miner_id="23", action="reboot")
        self.assertTrue(bool(token))
        self.assertEqual(len(token), 6)

        # First consumption must succeed
        valid, miner_id, reason = self.registry.consume_token(token)
        self.assertTrue(valid)
        self.assertEqual(miner_id, "23")
        self.assertEqual(reason, "ok")

        # Second consumption must fail (single-use)
        valid, miner_id, reason = self.registry.consume_token(token)
        self.assertFalse(valid)
        self.assertIsNone(miner_id)
        self.assertEqual(reason, "token_not_found")

    def test_token_registry_expiration(self):
        token = self.registry.create_token(miner_id="24", action="reboot")
        
        # Artificially age the token
        entry = self.registry._tokens[token]
        self.registry._tokens[token] = (entry[0], entry[1], time.time() - 65.0)

        valid, miner_id, reason = self.registry.consume_token(token)
        self.assertFalse(valid)
        self.assertEqual(reason, "token_expired")

    def test_token_registry_capacity_bounding(self):
        # Max capacity is 5
        tokens = [self.registry.create_token(miner_id=str(i), action="reboot") for i in range(10)]
        self.assertLessEqual(len(self.registry._tokens), 5)
        
        # Oldest tokens must have been pruned
        valid, _, reason = self.registry.consume_token(tokens[0])
        self.assertFalse(valid)
        self.assertEqual(reason, "token_not_found")

        # Most recent token must exist
        valid, miner_id, reason = self.registry.consume_token(tokens[-1])
        self.assertTrue(valid)
        self.assertEqual(miner_id, "9")

    def test_build_alert_keyboard_schema(self):
        kb = build_alert_keyboard(miner_id="23")
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        self.assertEqual(len(rows), 2)
        
        # Row 1: Diagnosticar, Gráfico
        row1 = rows[0]
        self.assertEqual(len(row1), 2)
        self.assertIn("Diagnosticar", row1[0]["text"])
        self.assertEqual(row1[0]["callback_data"], "diag:23")
        self.assertIn("Gráfico", row1[1]["text"])
        self.assertEqual(row1[1]["callback_data"], "chart:23")

        # Row 2: Reiniciar, Silenciar
        row2 = rows[1]
        self.assertEqual(len(row2), 2)
        self.assertIn("Reiniciar", row2[0]["text"])
        self.assertEqual(row2[0]["callback_data"], "rb_req:23")
        self.assertIn("Silenciar", row2[1]["text"])
        self.assertEqual(row2[1]["callback_data"], "snz:23:60")

    def test_build_confirmation_keyboard_schema(self):
        kb = build_confirmation_keyboard(miner_id="23", token="tok123")
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        self.assertEqual(len(rows), 2)
        
        # Confirm button
        self.assertIn("CONFIRMAR", rows[0][0]["text"])
        self.assertEqual(rows[0][0]["callback_data"], "rb_cfm:tok123:23")

        # Cancel button
        self.assertIn("Cancelar", rows[1][0]["text"])
        self.assertEqual(rows[1][0]["callback_data"], "rb_ccl:23")

    def test_build_settled_keyboard_schema(self):
        kb = build_settled_keyboard("Reinicio Solicitado")
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0]["text"], "Reinicio Solicitado")
        self.assertEqual(rows[0][0]["callback_data"], "noop")


from unittest.mock import MagicMock, patch
import threading
from pathlib import Path
from app.miner_monitor import _handle_callback_query, MinerState


class TestCallbackDispatcherIntegration(unittest.TestCase):
    def setUp(self):
        self.bot_token = "dummy_token"
        self.chat_id = "1206728163"
        self.config = {
            "telegram": {"bot_token": self.bot_token, "chat_id": 1206728163},
            "miners": [{"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028}],
        }
        self.miners = self.config["miners"]
        self.states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState()
        }
        self.state_lock = threading.Lock()
        self.token_registry = CallbackTokenRegistry(ttl_seconds=60.0, max_tokens=10)

    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.miner_monitor.run_hashcore_cli")
    def test_unauthorized_callback_rejected(self, mock_run_hashcore, mock_answer_cb):
        cb_query = {
            "id": "cb_100",
            "from": {"id": 9999999},  # Unauthorized
            "data": "rb_req:23",
            "message": {"message_id": 42, "chat": {"id": 9999999}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token,
            "cb_100",
            text="⛔ Acceso no autorizado",
            show_alert=True,
        )
        mock_run_hashcore.assert_not_called()

    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.miner_monitor.run_hashcore_cli")
    def test_expired_token_rejected(self, mock_run_hashcore, mock_answer_cb):
        # Create token with ttl=0 to force expiration
        expired_registry = CallbackTokenRegistry(ttl_seconds=0.0)
        token = expired_registry.create_token("23")
        time.sleep(0.01)

        cb_query = {
            "id": "cb_101",
            "from": {"id": 1206728163},
            "data": f"rb_cfm:{token}:23",
            "message": {"message_id": 42, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=expired_registry,
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token,
            "cb_101",
            text="⏱️ El token de confirmación ha expirado.",
            show_alert=True,
        )
        mock_run_hashcore.assert_not_called()

    @patch("app.miner_monitor.edit_message_reply_markup")
    @patch("app.miner_monitor.answer_callback_query")
    def test_rb_req_flow_presents_confirmation(self, mock_answer_cb, mock_edit_markup):
        cb_query = {
            "id": "cb_102",
            "from": {"id": 1206728163},
            "data": "rb_req:23",
            "message": {"message_id": 42, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token,
            "cb_102",
            text="⚠️ Confirmación requerida (expira en 60s)",
        )
        mock_edit_markup.assert_called_once()
        args = mock_edit_markup.call_args[0]
        self.assertEqual(args[0], self.bot_token)
        self.assertEqual(args[1], "1206728163")
        self.assertEqual(args[2], 42)
        # Verify reply markup contains confirmation button
        markup = args[3]
        self.assertIn("inline_keyboard", markup)
        self.assertIn("CONFIRMAR REINICIO", markup["inline_keyboard"][0][0]["text"])

    @patch("app.miner_monitor.edit_message_reply_markup")
    @patch("app.miner_monitor.answer_callback_query")
    def test_rb_ccl_flow_restores_keyboard(self, mock_answer_cb, mock_edit_markup):
        # First register a token
        self.token_registry.create_token("23")
        cb_query = {
            "id": "cb_103",
            "from": {"id": 1206728163},
            "data": "rb_ccl:23",
            "message": {"message_id": 42, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=self.token_registry,
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token,
            "cb_103",
            text="❌ Reinicio cancelado",
        )
        mock_edit_markup.assert_called_once()
        args = mock_edit_markup.call_args[0]
        markup = args[3]
        self.assertIn("Diagnosticar", markup["inline_keyboard"][0][0]["text"])

    @patch("app.miner_monitor.run_hashcore_cli")
    @patch("app.miner_monitor.edit_message_reply_markup")
    @patch("app.miner_monitor.answer_callback_query")
    def test_rb_cfm_valid_executes_reboot(self, mock_answer_cb, mock_edit_markup, mock_run_hashcore):
        mock_run_hashcore.return_value = (True, "OK")
        token = self.token_registry.create_token("23")

        cb_query = {
            "id": "cb_104",
            "from": {"id": 1206728163},
            "data": f"rb_cfm:{token}:23",
            "message": {"message_id": 42, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.token_registry,
        )
        mock_run_hashcore.assert_called_once()
        mock_edit_markup.assert_called_once()
        # Verify settled markup
        markup = mock_edit_markup.call_args[0][3]
        self.assertIn("Reinicio Iniciado", markup["inline_keyboard"][0][0]["text"])


class TestHelpCenterCallbacksIntegration(unittest.TestCase):
    def setUp(self):
        self.bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        self.chat_id = "1206728163"
        self.config = {"chat_id": self.chat_id}
        self.miners = []
        self.states = {}
        self.state_lock = unittest.mock.MagicMock()

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_help_nav_home_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_help_1",
            "from": {"id": 1206728163},
            "data": "help:nav:home",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_help_1")
        mock_edit_text.assert_called_once()
        args = mock_edit_text.call_args
        self.assertEqual(args[0][0], self.bot_token)
        self.assertEqual(args[0][1], "1206728163")
        self.assertEqual(args[0][2], 99)
        self.assertIn("CENTRO DE AYUDA", args[0][3])
        self.assertIn("reply_markup", args[1])

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_help_cat_thm_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_help_2",
            "from": {"id": 1206728163},
            "data": "help:cat:thm",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_help_2")
        mock_edit_text.assert_called_once()
        text = mock_edit_text.call_args[0][3]
        self.assertIn("TÉRMICO", text)
        self.assertIn("/fans", text)
        self.assertIn("/silent", text)

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_help_cmd_silent_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_help_3",
            "from": {"id": 1206728163},
            "data": "help:cmd:silent",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_help_3")
        mock_edit_text.assert_called_once()
        text = mock_edit_text.call_args[0][3]
        self.assertIn("/SILENT", text)
        self.assertIn("silencio", text.lower())

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_help_unauthorized_rejection(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_help_unauth",
            "from": {"id": 999999},  # Unauthorized user
            "data": "help:nav:home",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token, "cb_help_unauth", text="⛔ Acceso no autorizado", show_alert=True
        )
        mock_edit_text.assert_not_called()

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_help_malformed_callback(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_help_bad",
            "from": {"id": 1206728163},
            "data": "help:invalid:target",
            "message": {"message_id": 99, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token, "cb_help_bad", text="⚠️ Opción no reconocida."
        )
        mock_edit_text.assert_not_called()


class TestDiagnosticCallbacksIntegration(unittest.TestCase):
    def setUp(self):
        self.bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        self.chat_id = "1206728163"
        self.config = {
            "chat_id": self.chat_id,
            "miners": [
                {"name": "S19JPRO-23", "host": "192.168.1.23", "port": 4028},
                {"name": "S19JPRO-24", "host": "192.168.1.24", "port": 4028},
            ],
            "sqlite_db_path": ":memory:",
        }
        self.miners = self.config["miners"]
        from app.miner_monitor import MinerState
        st1 = MinerState()
        st1.state = "OK"
        st1.last_rate_ths = 104.2
        st1.last_max_chip_temp = 68.5
        st1.last_fan_duty_percent = 85.0
        st1.last_power_w = 3100.0
        st1.last_efficiency_j_th = 29.7

        st2 = MinerState()
        st2.state = "OK"
        st2.last_rate_ths = 102.1
        st2.last_max_chip_temp = 71.0
        st2.last_fan_duty_percent = 88.0
        st2.last_power_w = 3050.0
        st2.last_efficiency_j_th = 29.8

        self.states = {
            "S19JPRO-23|192.168.1.23:4028": st1,
            "S19JPRO-24|192.168.1.24:4028": st2,
        }
        self.state_lock = unittest.mock.MagicMock()

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_ref_status_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_status",
            "from": {"id": 1206728163},
            "data": "diag:ref:status",
            "message": {"message_id": 101, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_diag_status")
        mock_edit_text.assert_called_once()
        args, kwargs = mock_edit_text.call_args
        self.assertEqual(args[0], self.bot_token)
        self.assertEqual(args[1], "1206728163")
        self.assertEqual(args[2], 101)
        self.assertIn("ESTADO DE FLOTA", args[3])
        self.assertIn("reply_markup", kwargs)
        markup = kwargs["reply_markup"]
        cb_buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        self.assertIn("diag:ref:status", cb_buttons)

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_ref_fans_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_fans",
            "from": {"id": 1206728163},
            "data": "diag:ref:fans",
            "message": {"message_id": 102, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_diag_fans")
        mock_edit_text.assert_called_once()
        text = mock_edit_text.call_args[0][3]
        self.assertIn("ENFRIAMIENTO", text.upper())
        markup = mock_edit_text.call_args[1]["reply_markup"]
        cb_buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        self.assertIn("diag:ref:fans", cb_buttons)

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_ref_eff_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_eff",
            "from": {"id": 1206728163},
            "data": "diag:ref:eff",
            "message": {"message_id": 103, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_diag_eff")
        mock_edit_text.assert_called_once()
        text = mock_edit_text.call_args[0][3]
        self.assertIn("EFICIENCIA", text.upper())
        markup = mock_edit_text.call_args[1]["reply_markup"]
        cb_buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        self.assertIn("diag:ref:eff", cb_buttons)

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_ref_presets_dispatch(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_presets",
            "from": {"id": 1206728163},
            "data": "diag:ref:presets",
            "message": {"message_id": 104, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(self.bot_token, "cb_diag_presets")
        mock_edit_text.assert_called_once()
        text = mock_edit_text.call_args[0][3]
        self.assertIn("PERFILES", text.upper())
        markup = mock_edit_text.call_args[1]["reply_markup"]
        cb_buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        self.assertIn("diag:ref:presets", cb_buttons)

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_unauthorized_rejection(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_unauth",
            "from": {"id": 888888},
            "data": "diag:ref:status",
            "message": {"message_id": 105, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token, "cb_diag_unauth", text="⛔ Acceso no autorizado", show_alert=True
        )
        mock_edit_text.assert_not_called()

    @unittest.mock.patch("app.miner_monitor.edit_message_text")
    @unittest.mock.patch("app.miner_monitor.answer_callback_query")
    def test_diag_malformed_callback(self, mock_answer_cb, mock_edit_text):
        from app.miner_monitor import _handle_callback_query
        from pathlib import Path

        cb_query = {
            "id": "cb_diag_bad",
            "from": {"id": 1206728163},
            "data": "diag:bad:payload",
            "message": {"message_id": 106, "chat": {"id": 1206728163}},
        }
        _handle_callback_query(
            cb_query,
            config=self.config,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=Path("app/state.json"),
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=False,
            token_registry=unittest.mock.MagicMock(),
        )
        mock_answer_cb.assert_called_once_with(
            self.bot_token, "cb_diag_bad", text="⚠️ Opción no reconocida."
        )
        mock_edit_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
