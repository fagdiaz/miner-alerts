"""Unit and Integration tests for /flash_vnish Telegram Command, Callbacks and Pipeline (Spec 076)."""

from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from app.telegram.callbacks import (
    CallbackTokenRegistry,
    build_callback_data,
    parse_callback_data,
)
from app.telegram.commands.flash import (
    FlashVnishCommand,
    is_flash_in_progress,
    run_flash_and_provision_pipeline,
    _FLASH_JOBS_LOCK,
    _RUNNING_FLASH_JOBS,
)
from app.telegram.context import TelegramRequestContext
from app.telegram.router import create_default_command_router


class TestTelegramFlashCommandAndCallbacks(unittest.TestCase):
    def setUp(self) -> None:
        self.state_lock = threading.Lock()
        self.state_path = Path("test_state.json")
        self.states = {}
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
        ]
        self.token_registry = CallbackTokenRegistry(ttl_seconds=60.0, max_tokens=10)
        self.config = {
            "telegram": {"chat_id": 1206728163, "admin_user_ids": [1206728163]},
            "vnish_api_password": "test_password",
        }
        self.context = TelegramRequestContext(
            bot_token="TEST_BOT_TOKEN",
            chat_id="1206728163",
            config=self.config,
            miners=self.miners,
            states=self.states,
            state_lock=self.state_lock,
            state_path=self.state_path,
            token_registry=self.token_registry,
        )
        self.cmd = FlashVnishCommand()
        # Clean running jobs
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS.clear()

    def tearDown(self) -> None:
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS.clear()

    # --- 1. Router Registration ---
    def test_router_registration(self) -> None:
        router = create_default_command_router()
        handler = router.find_handler("flash_vnish")
        self.assertIsNotNone(handler)
        self.assertIsInstance(handler, FlashVnishCommand)
        # Check aliases
        self.assertIs(router.find_handler("flash"), handler)
        self.assertIs(router.find_handler("/flash"), handler)
        self.assertIs(router.find_handler("flashear"), handler)
        self.assertIs(router.find_handler("instalar_firmware"), handler)

    # --- 2. Callback Data Parsing and Length Limits ---
    def test_callback_format_and_length(self) -> None:
        cfm_data = build_callback_data("flash_cfm", "S19JPRO-24", token="tok123")
        self.assertEqual(cfm_data, "flash_cfm:tok123:S19JPRO-24")
        self.assertLessEqual(len(cfm_data.encode("utf-8")), 64)

        ccl_data = build_callback_data("flash_ccl", "S19JPRO-24")
        self.assertEqual(ccl_data, "flash_ccl:S19JPRO-24")
        self.assertLessEqual(len(ccl_data.encode("utf-8")), 64)

        action_cfm = parse_callback_data(cfm_data)
        self.assertIsNotNone(action_cfm)
        self.assertEqual(action_cfm.action_type, "flash_cfm")
        self.assertEqual(action_cfm.miner_id, "S19JPRO-24")
        self.assertEqual(action_cfm.token, "tok123")

        action_ccl = parse_callback_data(ccl_data)
        self.assertIsNotNone(action_ccl)
        self.assertEqual(action_ccl.action_type, "flash_ccl")
        self.assertEqual(action_ccl.miner_id, "S19JPRO-24")

    # --- 3. Command Help & Validation ---
    def test_command_no_args_displays_help(self) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            res = self.cmd.handle(self.context, [])
            self.assertTrue(res)
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertIn("FLASHEO REMOTO VNISH 1.2.6 NAND", args[0])
            self.assertEqual(kwargs.get("msg_type"), "INFO")

    def test_command_unknown_miner_displays_warning(self) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            res = self.cmd.handle(self.context, ["99"])
            self.assertTrue(res)
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertIn("no encontrado", args[0])
            self.assertEqual(kwargs.get("msg_type"), "WARNING")

    def test_command_unconfirmed_sends_confirmation_prompt_with_keyboard(self) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            res = self.cmd.handle(self.context, ["24"])
            self.assertTrue(res)
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertIn("CONFIRMACIÓN DE FLASHEO DE FIRMWARE", args[0])
            self.assertIn("192.168.100.24", args[0])
            self.assertIn("reply_markup", kwargs)
            keyboard = kwargs["reply_markup"]["inline_keyboard"]
            self.assertEqual(len(keyboard), 2)
            self.assertTrue(keyboard[0][0]["callback_data"].startswith("flash_cfm:"))
            self.assertEqual(keyboard[1][0]["callback_data"], "flash_ccl:S19JPRO-24")

    def test_command_already_running_displays_warning(self) -> None:
        dummy_thread = threading.Thread(target=lambda: time.sleep(0.5))
        dummy_thread.start()
        with _FLASH_JOBS_LOCK:
            _RUNNING_FLASH_JOBS["S19JPRO-24"] = dummy_thread

        try:
            self.assertTrue(is_flash_in_progress("S19JPRO-24"))
            with patch.object(self.context, "send_message") as mock_send:
                res = self.cmd.handle(self.context, ["24"])
                self.assertTrue(res)
                mock_send.assert_called_once()
                args, kwargs = mock_send.call_args
                self.assertIn("Ya existe un flasheo en progreso", args[0])
                self.assertEqual(kwargs.get("msg_type"), "WARNING")
        finally:
            dummy_thread.join()

    # --- 4. Confirmed Dispatch ---
    @patch("threading.Thread.start")
    def test_command_confirmed_dispatches_background_worker(self, mock_thread_start) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            res = self.cmd.handle(self.context, ["24", "CONFIRM"])
            self.assertTrue(res)
            mock_thread_start.assert_called_once()
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertIn("Flasheo iniciado en segundo plano", args[0])
            self.assertEqual(kwargs.get("msg_type"), "INFO")

            # Check that job is recorded
            self.assertIn("S19JPRO-24", _RUNNING_FLASH_JOBS)

    # --- 5. Pipeline Execution Edge Cases & Happy Path ---
    @patch("app.telegram.commands.flash.is_stock_bitmain", return_value=False)
    def test_pipeline_aborts_if_not_stock_bitmain(self, mock_is_stock) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            run_flash_and_provision_pipeline("192.168.100.24", "S19JPRO-24", self.context)
            mock_is_stock.assert_called_once_with("192.168.100.24")
            # Must notify probe and then abort
            self.assertEqual(mock_send.call_count, 2)
            abort_call = mock_send.call_args_list[1]
            self.assertIn("ABORTADO", abort_call[0][0])
            self.assertEqual(abort_call[1].get("msg_type"), "WARNING")

    @patch("app.telegram.commands.flash.is_stock_bitmain", return_value=True)
    @patch("app.telegram.commands.flash.flash_bitmain_nand", return_value=(False, "Connection reset by peer"))
    def test_pipeline_aborts_if_flash_fails(self, mock_flash, mock_is_stock) -> None:
        with patch.object(self.context, "send_message") as mock_send:
            run_flash_and_provision_pipeline("192.168.100.24", "S19JPRO-24", self.context)
            mock_is_stock.assert_called_once()
            mock_flash.assert_called_once()
            # Must notify probe, upload, and then failure
            self.assertEqual(mock_send.call_count, 3)
            fail_call = mock_send.call_args_list[2]
            self.assertIn("FALLO", fail_call[0][0])
            self.assertIn("Connection reset by peer", fail_call[0][0])
            self.assertEqual(fail_call[1].get("msg_type"), "ERROR")

    @patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
    @patch("time.sleep", return_value=None)
    @patch("time.time")
    @patch("app.telegram.commands.flash.is_stock_bitmain", return_value=True)
    @patch("app.telegram.commands.flash.flash_bitmain_nand", return_value=(True, "Tarball uploaded"))
    def test_pipeline_handles_boot_timeout(self, mock_flash, mock_is_stock, mock_time, mock_sleep, mock_urlopen) -> None:
        # Mock time progressing past the 150s deadline
        current_time = [1000.0]
        def fake_time():
            t = current_time[0]
            current_time[0] += 60.0
            return t
        mock_time.side_effect = fake_time

        with patch.object(self.context, "send_message") as mock_send:
            run_flash_and_provision_pipeline("192.168.100.24", "S19JPRO-24", self.context)
            # Must notify probe, upload, boot-wait, and timeout warning
            self.assertEqual(mock_send.call_count, 4)
            timeout_call = mock_send.call_args_list[3]
            self.assertIn("TIEMPO AGOTADO", timeout_call[0][0])
            self.assertEqual(timeout_call[1].get("msg_type"), "WARNING")

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    @patch("app.telegram.commands.flash.is_stock_bitmain", return_value=True)
    @patch("app.telegram.commands.flash.flash_bitmain_nand", return_value=(True, "Tarball uploaded"))
    @patch("app.telegram.commands.flash.provision_miner_from_profile", return_value=(False, "Pool apply failed: 500 Internal Error"))
    def test_pipeline_partial_provisioning_warning(self, mock_prov, mock_flash, mock_is_stock, mock_sleep, mock_urlopen) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.object(self.context, "send_message") as mock_send:
            run_flash_and_provision_pipeline("192.168.100.24", "S19JPRO-24", self.context)
            mock_is_stock.assert_called_once()
            mock_flash.assert_called_once()
            mock_prov.assert_called_once()

            # Check partial provisioning warning
            last_call = mock_send.call_args_list[-1]
            self.assertIn("APROVISIONAMIENTO PARCIAL", last_call[0][0])
            self.assertIn("Pool apply failed", last_call[0][0])
            self.assertEqual(last_call[1].get("msg_type"), "WARNING")

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    @patch("app.telegram.commands.flash.is_stock_bitmain", return_value=True)
    @patch("app.telegram.commands.flash.flash_bitmain_nand", return_value=(True, "Tarball uploaded"))
    @patch("app.telegram.commands.flash.provision_miner_from_profile", return_value=(True, "Pools, preset 2300W and 378 chip tune restored"))
    def test_pipeline_happy_path(self, mock_prov, mock_flash, mock_is_stock, mock_sleep, mock_urlopen) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.object(self.context, "send_message") as mock_send:
            run_flash_and_provision_pipeline("192.168.100.24", "S19JPRO-24", self.context)
            mock_is_stock.assert_called_once()
            mock_flash.assert_called_once()
            mock_prov.assert_called_once_with("192.168.100.24", "S19JPRO-24", password="test_password", restart_after=True)

            # Success message
            last_call = mock_send.call_args_list[-1]
            self.assertIn("FLASHEO & APROVISIONAMIENTO EXITOSO", last_call[0][0])
            self.assertIn("S19JPRO-24", last_call[0][0])
            self.assertEqual(last_call[1].get("msg_type"), "SUCCESS")

            # Clean job tracking
            self.assertNotIn("S19JPRO-24", _RUNNING_FLASH_JOBS)


if __name__ == "__main__":
    unittest.main()
