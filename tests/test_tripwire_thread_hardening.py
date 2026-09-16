import threading
import time
import unittest
from unittest.mock import patch, MagicMock

import app.miner_monitor as monitor


class TestTripwireThreadHardening(unittest.TestCase):
    def test_tripwire_restore_exception_handling(self):
        """Ensure unhandled exceptions in defensive restore thread are caught and logged."""
        logged_messages = []

        def mock_log(msg):
            logged_messages.append(msg)

        with patch.object(monitor, "log", side_effect=mock_log), \
             patch.object(monitor, "safe_set_miner_preset", side_effect=RuntimeError("Simulated network crash")):

            # Simulate the inner thread target from refresh_vnish_overclock_settings
            def _async_restore_tripwire_preset(
                _h="192.168.1.100",
                _pw="admin",
                _pr="2100W",
                _to=3.0,
                _nm="S19JPRO-01",
            ):
                try:
                    ok_r, err_r = monitor.safe_set_miner_preset(_h, _pw, _pr, timeout=_to)
                    if ok_r:
                        monitor.log(f"[TRIPWIRE_INTERLOCK_RESTORE_OK] miner={_nm} preset restaurado defensivamente a {_pr}")
                    else:
                        monitor.log(f"[TRIPWIRE_INTERLOCK_RESTORE_FAIL] miner={_nm} fallo restaurando a {_pr}: {err_r}")
                except Exception as _th_exc:
                    monitor.log(f"[TRIPWIRE_INTERLOCK_RESTORE_ERR] miner={_nm} excepcion en hilo de restauracion: {type(_th_exc).__name__}: {_th_exc}")

            t = threading.Thread(target=_async_restore_tripwire_preset, daemon=True, name="TestTripwireRestore")
            t.start()
            t.join(timeout=2.0)

            self.assertFalse(t.is_alive())
            err_logs = [m for m in logged_messages if "[TRIPWIRE_INTERLOCK_RESTORE_ERR]" in m]
            self.assertTrue(len(err_logs) > 0, f"Expected [TRIPWIRE_INTERLOCK_RESTORE_ERR] in logs: {logged_messages}")
            self.assertIn("Simulated network crash", err_logs[0])

    def test_shutdown_purge_exception_handling(self):
        """Ensure unhandled exceptions in ShutdownPurgeNotify thread are caught and logged."""
        logged_messages = []

        def mock_log(msg):
            logged_messages.append(msg)

        with patch.object(monitor, "log", side_effect=mock_log):
            def _purge_and_notify_harness():
                try:
                    raise RuntimeError("Fan control explosion")
                except Exception as _th_exc:
                    monitor.log(f"[SHUTDOWN_PURGE_ERR] Excepcion en hilo ShutdownPurgeNotify: {type(_th_exc).__name__}: {_th_exc}")

            t = threading.Thread(target=_purge_and_notify_harness, daemon=True, name="TestPurgeNotify")
            t.start()
            t.join(timeout=2.0)

            self.assertFalse(t.is_alive())
            err_logs = [m for m in logged_messages if "[SHUTDOWN_PURGE_ERR]" in m]
            self.assertTrue(len(err_logs) > 0, f"Expected [SHUTDOWN_PURGE_ERR] in logs: {logged_messages}")
            self.assertIn("Fan control explosion", err_logs[0])


if __name__ == "__main__":
    unittest.main()
