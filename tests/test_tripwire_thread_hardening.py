import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import app.miner_monitor as monitor
from app.governance.fleet_shutdown import OperationResult
from app.telegram.callbacks import CallbackTokenRegistry


class TestTripwireThreadHardening(unittest.TestCase):
    """
    Exhaustive QA tests verifying thread hardening and exception containment
    for asynchronous daemon threads in miner_monitor.py:
    1. _async_restore_tripwire_preset (spawned in refresh_vnish_overclock_settings)
    2. ShutdownPurgeNotify (spawned in _handle_command_center_callback)
    """

    def test_tripwire_restore_production_exception_handling(self):
        """Verify production _async_restore_tripwire_preset catches and logs unhandled exceptions."""
        logged_messages = []

        def mock_log(msg):
            logged_messages.append(msg)

        miners = [{"name": "S19JPRO-01", "host": "192.168.1.100", "port": 4028}]
        sk = "S19JPRO-01|192.168.1.100:4028"
        st = monitor.MinerState()
        st.hw_error_lock_until_ts = 2000.0
        st.hw_error_locked_preset = "2100W"
        st.vnish_discovered_preset = "2100W"
        states = {sk: st}
        state_lock = threading.Lock()

        # Mock safe_get_overclock_settings returning a higher preset (2800W > 2100W locked)
        mock_overclock = (True, {"preset": "2800W", "top_preset": "2800W", "switcher_enabled": False, "target_power_w": 2800}, None)

        spawned = None
        orig_thread = threading.Thread

        def _capture_thread(*args, **kwargs):
            nonlocal spawned
            th = orig_thread(*args, **kwargs)
            if kwargs.get("name") == "RestoreLock_S19JPRO-01":
                spawned = th
            return th

        with patch.object(monitor, "log", side_effect=mock_log), \
             patch.object(monitor, "safe_get_overclock_settings", return_value=mock_overclock), \
             patch.object(monitor, "safe_set_miner_preset", side_effect=RuntimeError("Simulated network crash")), \
             patch("threading.Thread", side_effect=_capture_thread):

            monitor.refresh_vnish_overclock_settings(
                miners=miners,
                states=states,
                state_lock=state_lock,
                vnish_pw="admin",
                timeout=1.0,
                force=True,
                now_ts=1000.0,
            )

        self.assertIsNotNone(spawned, "RestoreLock_S19JPRO-01 thread should have been spawned")
        spawned.join(timeout=3.0)
        self.assertFalse(spawned.is_alive())

        # Verify log messages
        interlock_logs = [m for m in logged_messages if "[TRIPWIRE_INTERLOCK]" in m]
        self.assertTrue(len(interlock_logs) > 0, f"Expected [TRIPWIRE_INTERLOCK] in logs: {logged_messages}")

        err_logs = [m for m in logged_messages if "[TRIPWIRE_INTERLOCK_RESTORE_ERR]" in m]
        self.assertTrue(len(err_logs) > 0, f"Expected [TRIPWIRE_INTERLOCK_RESTORE_ERR] in logs: {logged_messages}")
        self.assertIn("Simulated network crash", err_logs[0])

    def test_tripwire_restore_production_ok_and_fail(self):
        """Verify production _async_restore_tripwire_preset logs OK or FAIL correctly."""
        miners = [{"name": "S19JPRO-02", "host": "192.168.1.102", "port": 4028}]
        sk = "S19JPRO-02|192.168.1.102:4028"
        mock_overclock = (True, {"preset": "2800W", "top_preset": "2800W", "switcher_enabled": False, "target_power_w": 2800}, None)
        orig_thread = threading.Thread

        # Case 1: OK
        logged_ok = []
        st_ok = monitor.MinerState()
        st_ok.hw_error_lock_until_ts = 2000.0
        st_ok.hw_error_locked_preset = "2100W"
        st_ok.vnish_discovered_preset = "2100W"
        spawned_ok = None

        def _cap_ok(*args, **kwargs):
            nonlocal spawned_ok
            th = orig_thread(*args, **kwargs)
            if kwargs.get("name") == "RestoreLock_S19JPRO-02":
                spawned_ok = th
            return th

        with patch.object(monitor, "log", side_effect=logged_ok.append), \
             patch.object(monitor, "safe_get_overclock_settings", return_value=mock_overclock), \
             patch.object(monitor, "safe_set_miner_preset", return_value=(True, None)), \
             patch("threading.Thread", side_effect=_cap_ok):
            monitor.refresh_vnish_overclock_settings(
                miners=miners,
                states={sk: st_ok},
                state_lock=threading.Lock(),
                vnish_pw="admin",
                timeout=1.0,
                force=True,
                now_ts=1000.0,
            )
        if spawned_ok:
            spawned_ok.join(timeout=3.0)
            self.assertFalse(spawned_ok.is_alive())
        self.assertTrue(any("[TRIPWIRE_INTERLOCK_RESTORE_OK]" in m for m in logged_ok))

        # Case 2: FAIL
        logged_fail = []
        st_fail = monitor.MinerState()
        st_fail.hw_error_lock_until_ts = 2000.0
        st_fail.hw_error_locked_preset = "2100W"
        st_fail.vnish_discovered_preset = "2100W"
        spawned_fail = None

        def _cap_fail(*args, **kwargs):
            nonlocal spawned_fail
            th = orig_thread(*args, **kwargs)
            if kwargs.get("name") == "RestoreLock_S19JPRO-02":
                spawned_fail = th
            return th

        with patch.object(monitor, "log", side_effect=logged_fail.append), \
             patch.object(monitor, "safe_get_overclock_settings", return_value=mock_overclock), \
             patch.object(monitor, "safe_set_miner_preset", return_value=(False, "Firmware rejected")), \
             patch("threading.Thread", side_effect=_cap_fail):
            monitor.refresh_vnish_overclock_settings(
                miners=miners,
                states={sk: st_fail},
                state_lock=threading.Lock(),
                vnish_pw="admin",
                timeout=1.0,
                force=True,
                now_ts=1000.0,
            )
        if spawned_fail:
            spawned_fail.join(timeout=3.0)
            self.assertFalse(spawned_fail.is_alive())
        self.assertTrue(any("[TRIPWIRE_INTERLOCK_RESTORE_FAIL]" in m for m in logged_fail))

    def test_shutdown_purge_production_exception_handling(self):
        """Verify production ShutdownPurgeNotify thread catches and logs exceptions without crashing."""
        logged_messages = []

        def mock_log(msg):
            logged_messages.append(msg)

        miners = [{"name": "M1", "host": "192.168.100.20", "port": 4028}]
        reg = CallbackTokenRegistry()
        token = reg.create_token("1", action="shutdown")

        cb_cfm = {
            "id": "cb_cfm_purge_test",
            "data": f"cc:act:sd_cfm:{token}:1",
            "message": {"message_id": 7001, "chat": {"id": 100}},
            "from": {"id": 100},
        }

        mock_shutdown_res = {
            "M1": OperationResult(
                miner_id="M1",
                success=True,
            )
        }
        mock_ramp_res = {
            "M1": OperationResult(
                miner_id="M1",
                success=True,
            )
        }

        spawned_purge = None
        orig_thread = threading.Thread

        def _cap_purge(*args, **kwargs):
            nonlocal spawned_purge
            th = orig_thread(*args, **kwargs)
            if kwargs.get("name") == "ShutdownPurgeNotify":
                spawned_purge = th
            return th

        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch.object(monitor, "log", side_effect=mock_log), \
             patch.object(monitor, "answer_callback_query"), \
             patch.object(monitor, "edit_message_text"), \
             patch.object(monitor, "send_telegram"), \
             patch("app.governance.fleet_shutdown.DEFAULT_PURGE_SECONDS", 0.0), \
             patch("time.sleep", return_value=None), \
             patch("app.governance.fleet_shutdown.execute_parallel_shutdown", return_value=mock_shutdown_res), \
             patch("app.governance.fleet_shutdown.execute_parallel_fan_duty", side_effect=[mock_ramp_res, RuntimeError("Fan control explosion")]), \
             patch("threading.Thread", side_effect=_cap_purge):

            monitor._handle_command_center_callback(
                cb_query=cb_cfm,
                config={"vnish_api_password": "admin"},
                bot_token="fake_token",
                chat_id="100",
                cb_chat_id=100,
                message_id=7001,
                cb_id="cb_cfm_purge_test",
                miners=miners,
                states={},
                state_lock=threading.Lock(),
                state_path=Path(tmp_dir) / "state.json",
                current_last_update_id=1,
                hashcore_cfg={},
                event_store=None,
                qa_mode=False,
                qa_allow_actions=True,
                token_registry=reg,
            )

        self.assertIsNotNone(spawned_purge, "ShutdownPurgeNotify thread should have been spawned")
        spawned_purge.join(timeout=3.0)
        self.assertFalse(spawned_purge.is_alive())

        err_logs = [m for m in logged_messages if "[SHUTDOWN_PURGE_ERR]" in m]
        self.assertTrue(len(err_logs) > 0, f"Expected [SHUTDOWN_PURGE_ERR] in logs: {logged_messages}")
        self.assertIn("Fan control explosion", err_logs[0])


if __name__ == "__main__":
    unittest.main()
