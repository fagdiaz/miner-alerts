"""Integration tests for Safe Fleet Shutdown & Multi-Select Maintenance Mode (Spec 048).

Validates end-to-end interactions between:
- State persistence (is_shutdown_maintenance, shutdown_maintenance_ts)
- Command center callback dispatchers (nav, toggle, all, clear, request, confirm, cancel, resume)
- Protection interlocks (manual reboot guard, governor skip, balancer skip)
- Status and snooze card annotations (⏸️ DETENIDO)
"""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.governance.fleet_shutdown import (
    OperationResult,
    extract_miner_identifier,
    make_empty_bitmask,
    make_full_bitmask,
    resolve_selected_miners,
    toggle_selection_bitmask,
)
from app.miner_monitor import (
    MinerState,
    _handle_command_center_callback,
    execute_governor_cycle,
    load_state,
    save_state,
)
from app.telegram.callbacks import CallbackTokenRegistry
from app.telegram.fleet_cards import _miner_state_badge, render_fleet_status_card
from app.telegram.snooze import build_snooze_status_text


class TestSafeFleetShutdownIntegration(unittest.TestCase):
    """Integration test suite covering Spec 048 functionality."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028},
        ]
        self.config = {
            "miners": self.miners,
            "vnish_api_password": "admin",
            "qa_mode": False,
        }
        self.lock = threading.Lock()
        self.reg = CallbackTokenRegistry()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_persistence_roundtrip(self):
        """Verify is_shutdown_maintenance and shutdown_maintenance_ts are saved and restored."""
        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
                shutdown_maintenance_ts=1700000000.0,
            ),
            "S19JPRO-24|192.168.100.24:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=False,
                shutdown_maintenance_ts=0.0,
            ),
        }
        save_state(self.state_path, states, last_update_id=123)
        loaded_states, last_up_id = load_state(self.state_path)

        self.assertEqual(last_up_id, 123)
        st23 = loaded_states["S19JPRO-23|192.168.100.23:4028"]
        self.assertTrue(st23.is_shutdown_maintenance)
        self.assertEqual(st23.shutdown_maintenance_ts, 1700000000.0)

        st24 = loaded_states["S19JPRO-24|192.168.100.24:4028"]
        self.assertFalse(st24.is_shutdown_maintenance)
        self.assertEqual(st24.shutdown_maintenance_ts, 0.0)

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_nav_shutdown_menu(self, mock_answer, mock_edit):
        """cc:nav:shutdown displays multi-select shutdown menu with all checkboxes unchecked."""
        cb_query = {
            "id": "cb_sd_nav",
            "data": "cc:nav:shutdown",
            "message": {"message_id": 5001, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5001,
            cb_id="cb_sd_nav",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        mock_answer.assert_called_once_with("fake_token", "cb_sd_nav")
        mock_edit.assert_called_once()
        args, _ = mock_edit.call_args
        self.assertIn("PARADA SEGURA: SELECCIÓN", args[3])
        self.assertIn("Marcados*: (ninguno)", args[3])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_nav_resume_menu(self, mock_answer, mock_edit):
        """cc:nav:resume displays resume menu."""
        cb_query = {
            "id": "cb_res_nav",
            "data": "cc:nav:resume",
            "message": {"message_id": 5002, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5002,
            cb_id="cb_res_nav",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        mock_answer.assert_called_once_with("fake_token", "cb_res_nav")
        mock_edit.assert_called_once()
        args, _ = mock_edit.call_args
        self.assertIn("REANUDAR MINADO", args[3])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_sd_tog_updates_mask(self, mock_answer, mock_edit):
        """cc:act:sd_tog:23:1000 toggles miner 23 and updates UI with checkmark."""
        cb_query = {
            "id": "cb_sd_tog",
            "data": "cc:act:sd_tog:23:1000",
            "message": {"message_id": 5003, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_query,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5003,
            cb_id="cb_sd_tog",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        mock_edit.assert_called_once()
        args, kwargs = mock_edit.call_args
        self.assertIn("Marcados*: 23", args[3])
        reply_markup = kwargs.get("reply_markup") or {}
        kb_text = str(reply_markup)
        self.assertIn("☑️ S19-23", kb_text)
        self.assertIn("APAGAR SELECCIONADOS (1)", kb_text)

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_sd_all_and_clear(self, mock_answer, mock_edit):
        """cc:act:sd_all selects all miners; cc:act:sd_clr unchecks all."""
        cb_all = {
            "id": "cb_all",
            "data": "cc:act:sd_all",
            "message": {"message_id": 5004, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_all,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5004,
            cb_id="cb_all",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        _, kwargs_all = mock_edit.call_args
        self.assertIn("APAGAR GRANJA (4)", str(kwargs_all))

        cb_clr = {
            "id": "cb_clr",
            "data": "cc:act:sd_clr",
            "message": {"message_id": 5004, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_clr,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5004,
            cb_id="cb_clr",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        args_clr, kwargs_clr = mock_edit.call_args
        self.assertIn("Marcados*: (ninguno)", args_clr[3])
        self.assertIn("Apagar Seleccionados (0)", str(kwargs_clr))

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_sd_req_zero_selected_shows_alert(self, mock_answer, mock_edit):
        """cc:act:sd_req:0000 with 0 selected triggers an alert popup and doesn't edit view."""
        cb_req = {
            "id": "cb_zero",
            "data": "cc:act:sd_req:0000",
            "message": {"message_id": 5005, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_req,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5005,
            cb_id="cb_zero",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        mock_answer.assert_any_call("fake_token", "cb_zero", text="⚠️ Marcá al menos un minero con las casillas ⬜.", show_alert=True)
        mock_edit.assert_not_called()

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_callback_sd_req_renders_confirmation_with_token(self, mock_answer, mock_edit):
        """cc:act:sd_req:1010 generates token and renders 2-step confirmation for 23 and 25."""
        cb_req = {
            "id": "cb_req_2",
            "data": "cc:act:sd_req:1010",
            "message": {"message_id": 5006, "chat": {"id": 100}},
            "from": {"id": 100},
        }
        _handle_command_center_callback(
            cb_query=cb_req,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5006,
            cb_id="cb_req_2",
            miners=self.miners,
            states={},
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )
        mock_edit.assert_called_once()
        args, kwargs = mock_edit.call_args
        self.assertIn("CONFIRMAR PARADA SEGURA", args[3])
        self.assertIn("S19JPRO-23", args[3])
        self.assertIn("S19JPRO-25", args[3])
        self.assertIn("sd_cfm:", str(kwargs))

    @patch("app.miner_monitor.send_telegram")
    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.governance.fleet_shutdown.execute_parallel_shutdown")
    def test_callback_sd_cfm_executes_shutdown(self, mock_exec_shutdown, mock_answer, mock_edit, mock_send_tg):
        """cc:act:sd_cfm executes shutdown, updates state to is_shutdown_maintenance, sets 4h snooze."""
        token = self.reg.create_token("1000", action="shutdown")
        mock_exec_shutdown.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }

        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(state="OK"),
            "S19JPRO-24|192.168.100.24:4028": MinerState(state="OK"),
        }

        cb_cfm = {
            "id": "cb_cfm",
            "data": f"cc:act:sd_cfm:{token}:1000",
            "message": {"message_id": 5007, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        _handle_command_center_callback(
            cb_query=cb_cfm,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5007,
            cb_id="cb_cfm",
            miners=self.miners,
            states=states,
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )

        mock_exec_shutdown.assert_called_once()
        mock_edit.assert_called_once()
        args, _ = mock_edit.call_args
        self.assertIn("PARADA EN PROGRESO", args[3])
        self.assertIn("23", args[3])

        st23 = states["S19JPRO-23|192.168.100.23:4028"]
        self.assertTrue(st23.is_shutdown_maintenance)
        self.assertGreater(st23.snooze_until_ts, time.time() + 3 * 3600)

        st24 = states["S19JPRO-24|192.168.100.24:4028"]
        self.assertFalse(st24.is_shutdown_maintenance)

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.governance.fleet_shutdown.execute_parallel_resume")
    def test_callback_resume_clears_maintenance_and_snooze(self, mock_exec_resume, mock_answer, mock_edit):
        """cc:act:resume:23 executes resume and clears maintenance and snooze."""
        mock_exec_resume.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }

        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
                snooze_until_ts=time.time() + 10000,
            ),
        }

        cb_res = {
            "id": "cb_res",
            "data": "cc:act:resume:23",
            "message": {"message_id": 5008, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        _handle_command_center_callback(
            cb_query=cb_res,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5008,
            cb_id="cb_res",
            miners=self.miners,
            states=states,
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )

        mock_exec_resume.assert_called_once()
        mock_edit.assert_called_once()
        args, _ = mock_edit.call_args
        self.assertIn("MINADO REANUDADO", args[3])

        st23 = states["S19JPRO-23|192.168.100.23:4028"]
        self.assertFalse(st23.is_shutdown_maintenance)
        self.assertIsNone(st23.snooze_until_ts)

    @patch("app.miner_monitor.threading.Thread")
    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.governance.fleet_shutdown.execute_parallel_fan_duty")
    @patch("app.governance.fleet_shutdown.execute_parallel_shutdown")
    def test_thermal_purge_ramp_and_acoustic_drop_integration(
        self,
        mock_exec_shutdown,
        mock_exec_fan,
        mock_answer,
        mock_edit,
        mock_thread_cls,
    ):
        """Verify 100% thermal purge ramp is dispatched on shutdown and 40% idle drop runs in thread (Spec 049)."""
        token = self.reg.create_token("1000", action="shutdown")
        mock_exec_shutdown.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }
        mock_exec_fan.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }

        thread_target = None
        mock_thread_inst = MagicMock()
        def _capture_thread(**kwargs):
            nonlocal thread_target
            thread_target = kwargs.get("target")
            return mock_thread_inst
        mock_thread_cls.side_effect = _capture_thread

        states = {"S19JPRO-23|192.168.100.23:4028": MinerState(state="OK")}
        cb_cfm = {
            "id": "cb_cfm_purge",
            "data": f"cc:act:sd_cfm:{token}:1000",
            "message": {"message_id": 6001, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        _handle_command_center_callback(
            cb_query=cb_cfm,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=6001,
            cb_id="cb_cfm_purge",
            miners=self.miners,
            states=states,
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )

        mock_exec_shutdown.assert_called_once()
        mock_exec_fan.assert_any_call([self.miners[0]], 100, "admin")

        args, _ = mock_edit.call_args
        self.assertIn("Rampa 100% activa", args[3])

        mock_thread_inst.start.assert_called_once()
        self.assertIsNotNone(thread_target)

        with patch("time.sleep") as mock_sleep, patch("app.miner_monitor.send_telegram") as mock_send_tg:
            thread_target()
            mock_sleep.assert_called_once_with(45)
            mock_exec_fan.assert_any_call([self.miners[0]], 40, "admin")
            mock_send_tg.assert_called_once()
            tg_args, _ = mock_send_tg.call_args
            self.assertIn("ÁREA ELÉCTRICA SEGURA", tg_args[2])
            self.assertIn("*Coolers*: Reposo (40% PWM)", tg_args[2])

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    @patch("app.governance.fleet_shutdown.execute_parallel_fan_duty")
    @patch("app.governance.fleet_shutdown.execute_parallel_resume")
    def test_resume_restores_active_fan_duty(self, mock_exec_resume, mock_exec_fan, mock_answer, mock_edit):
        """Verify resume calls execute_parallel_fan_duty with 100% to exit idle floor (Spec 049)."""
        mock_exec_resume.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }
        mock_exec_fan.return_value = {
            "23": OperationResult(miner_id="23", success=True),
        }

        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
            ),
        }

        cb_res = {
            "id": "cb_res_fan",
            "data": "cc:act:resume:23",
            "message": {"message_id": 6002, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        _handle_command_center_callback(
            cb_query=cb_res,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=6002,
            cb_id="cb_res_fan",
            miners=self.miners,
            states=states,
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )

        mock_exec_resume.assert_called_once()
        mock_exec_fan.assert_called_once_with([self.miners[0]], 100, "admin")

    @patch("app.miner_monitor.edit_message_text")
    @patch("app.miner_monitor.answer_callback_query")
    def test_reboot_blocked_on_stopped_miner(self, mock_answer, mock_edit):
        """Reboot request via command center is blocked if miner is stopped for maintenance."""
        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
            ),
        }

        cb_rb = {
            "id": "cb_rb_blocked",
            "data": "cc:act:rb_req:23",
            "message": {"message_id": 5009, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        _handle_command_center_callback(
            cb_query=cb_rb,
            config=self.config,
            bot_token="fake_token",
            chat_id="100",
            cb_chat_id=100,
            message_id=5009,
            cb_id="cb_rb_blocked",
            miners=self.miners,
            states=states,
            state_lock=self.lock,
            state_path=self.state_path,
            current_last_update_id=1,
            hashcore_cfg={},
            event_store=None,
            qa_mode=False,
            qa_allow_actions=True,
            token_registry=self.reg,
        )

        mock_answer.assert_any_call(
            "fake_token",
            "cb_rb_blocked",
            text="⚠️ Minero en Parada Segura (Mantenimiento). Usá /resume primero.",
            show_alert=True,
        )
        mock_edit.assert_not_called()

    def test_governor_skips_stopped_miner(self):
        """execute_governor_cycle skips miners with is_shutdown_maintenance=True."""
        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
                governor_last_temp_c=85.0,
                governor_duty=70,
            ),
        }
        config = {
            "fan_governor_enabled": True,
            "fan_governor_dry_run": True,
        }
        with patch("app.miner_monitor.compute_governor_step") as mock_compute:
            execute_governor_cycle(
                miners=self.miners[:1],
                states=states,
                state_lock=self.lock,
                config=config,
                now_ts=time.time(),
                qa_mode=False,
            )
            mock_compute.assert_not_called()

    def test_snooze_status_displays_detenido_tag(self):
        """build_snooze_status_text formats stopped miners with [⏸️ DETENIDO]."""
        states = {
            "S19JPRO-23|192.168.100.23:4028": MinerState(
                state="OK",
                is_shutdown_maintenance=True,
                snooze_until_ts=time.time() + 3600,
            ),
        }
        text = build_snooze_status_text(self.miners[:1], states)
        self.assertIn("[⏸️ DETENIDO]", text)
        self.assertIn("S19JPRO-23", text)

    def test_fleet_status_badge_and_lines_for_stopped_miner(self):
        """_miner_state_badge returns ⏸️ and render_fleet_status_card renders DETENIDO."""
        st = MinerState(state="OK", is_shutdown_maintenance=True)
        badge = _miner_state_badge(st)
        self.assertEqual(badge, "⏸️")

        states = {"S19JPRO-23|192.168.100.23:4028": st}
        text, _ = render_fleet_status_card(states, miners=self.miners[:1])
        self.assertIn("• Estado: ⏸️ DETENIDO", text)
        self.assertIn("• Modo: ⏸️ Parada Segura", text)


if __name__ == "__main__":
    unittest.main()
