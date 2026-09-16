"""Unit tests for the high-frequency IPC channel between monitor and watchdog (Spec 068)."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest

from app.ipc.watchdog_pipe import (
    DEFAULT_FALLBACK_PORT,
    IPCPingResult,
    WatchdogIPCClient,
    WatchdogIPCServer,
    dump_thread_frames,
)


class TestWatchdogIPC(unittest.TestCase):
    def setUp(self) -> None:
        self.test_pipe = rf"\\.\pipe\TestMinerAlertsWatchdog_{int(time.time() * 1000) % 1_000_000}"
        self.test_port = 14029 + (int(time.time() * 100) % 500)
        self.server: WatchdogIPCServer | None = None

    def tearDown(self) -> None:
        if self.server:
            self.server.stop(timeout_s=1.0)
            self.server = None

    def test_dump_thread_frames_creates_valid_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            target = dump_thread_frames(out_dir)
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("=== DEADLOCK FORENSICS DUMP", content)
            self.assertIn("Active threads count:", content)
            self.assertIn("Thread ID:", content)

    def test_ipc_result_tuple_and_attribute_access(self) -> None:
        res = IPCPingResult(
            ok=True,
            tick_sequence=42,
            uptime_s=123.45,
            last_tick_elapsed_s=0.015,
            nonce="abc",
            transport="pipe",
        )
        # 4-tuple unpacking
        ok, seq, up, err = res
        self.assertTrue(ok)
        self.assertEqual(seq, 42)
        self.assertEqual(up, 123.45)
        self.assertIsNone(err)

        # Attribute access
        self.assertEqual(res.ok, True)
        self.assertEqual(res.tick_sequence, 42)
        self.assertEqual(res.uptime_s, 123.45)
        self.assertEqual(res.last_tick_elapsed_s, 0.015)
        self.assertEqual(res.nonce, "abc")
        self.assertEqual(res.transport, "pipe")

    def test_ipc_server_socket_transport_roundtrip(self) -> None:
        ticks = [10]

        def get_status() -> tuple[int, float, float]:
            ticks[0] += 1
            return (ticks[0], 500.0, 0.035)

        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            get_status_callback=get_status,
        )
        self.server._run_socket_fallback = self.server._run_socket_fallback
        # Force server to use socket fallback
        self.server._run = self.server._run_socket_fallback
        self.server.start()

        client = WatchdogIPCClient(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.5,
            force_transport="socket",
        )

        res1 = client.ping("test1")
        self.assertTrue(res1.ok, f"Ping failed: {res1.error}")
        self.assertEqual(res1.tick_sequence, 11)
        self.assertAlmostEqual(res1.uptime_s, 500.0, places=1)
        self.assertAlmostEqual(res1.last_tick_elapsed_s, 0.035, places=2)
        self.assertEqual(res1.transport, "socket")

        res2 = client.ping("test2")
        self.assertTrue(res2.ok)
        self.assertEqual(res2.tick_sequence, 12)

    @unittest.skipUnless(os.name == "nt", "Named pipes require Windows NT")
    def test_ipc_server_named_pipe_roundtrip(self) -> None:
        ticks = [100]

        def get_status() -> tuple[int, float, float]:
            ticks[0] += 1
            return (ticks[0], 250.0, 0.042)

        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            get_status_callback=get_status,
        )
        self.server.start()
        self.assertEqual(self.server.active_transport, "pipe")

        client = WatchdogIPCClient(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.5,
            force_transport="pipe",
        )

        res = client.ping("nonce99")
        self.assertTrue(res.ok, f"Named pipe ping failed: {res.error}")
        self.assertEqual(res.tick_sequence, 101)
        self.assertEqual(res.nonce, "nonce99")
        self.assertEqual(res.transport, "pipe")

    def test_ipc_shutdown_wake_up_unblock(self) -> None:
        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
        )
        self.server.start()
        self.assertTrue(self.server.is_running)

        t0 = time.perf_counter()
        self.server.stop(timeout_s=1.0)
        elapsed = time.perf_counter() - t0
        self.assertFalse(self.server.is_running)
        # Must stop cleanly in less than 500 ms (contract is <200 ms)
        self.assertLess(elapsed, 0.5)

    def test_ipc_client_handles_unreachable_server(self) -> None:
        client = WatchdogIPCClient(
            pipe_name=rf"\\.\pipe\NonExistentPipe_{int(time.time())}",
            fallback_port=29999,
            timeout_s=0.05,
            force_transport="socket",
        )
        res = client.ping("dead")
        self.assertFalse(res.ok)
        self.assertTrue(any(w in (res.error or "").lower() for w in ("error", "timeout", "refused", "unavailable")))

    def test_ipc_deadlock_detection_via_stale_tick_sequence(self) -> None:
        # Simulate monitor where tick_sequence does not advance
        stale_tick = 50
        frozen_time = 100.0

        def frozen_status() -> tuple[int, float, float]:
            return (stale_tick, frozen_time, 0.05)

        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            get_status_callback=frozen_status,
        )
        self.server._run = self.server._run_socket_fallback
        self.server.start()

        client = WatchdogIPCClient(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            force_transport="socket",
        )

        res1 = client.ping()
        self.assertTrue(res1.ok)
        res2 = client.ping()
        self.assertTrue(res2.ok)

        # Confirm deadlock detection logic: tick_sequence is unchanged
        self.assertEqual(res1.tick_sequence, res2.tick_sequence)

    def test_forensics_dump_via_ipc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            self.server = WatchdogIPCServer(
                pipe_name=self.test_pipe,
                fallback_port=self.test_port,
                timeout_s=0.2,
                forensics_dir=out_dir,
            )
            self.server._run = self.server._run_socket_fallback
            self.server.start()

            client = WatchdogIPCClient(
                pipe_name=self.test_pipe,
                fallback_port=self.test_port,
                timeout_s=0.5,
                force_transport="socket",
            )
            ok, dump_path = client.request_forensics_dump()
            self.assertTrue(ok, f"Dump failed: {dump_path}")
            self.assertIsNotNone(dump_path)
            self.assertTrue(Path(dump_path).exists())

    def test_ipc_server_unknown_command(self) -> None:
        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
        )
        self.server._run = self.server._run_socket_fallback
        self.server.start()

        client = WatchdogIPCClient(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.5,
            force_transport="socket",
        )
        ok, resp = client._send_cmd_socket("FOOBAR\n")
        self.assertFalse(ok)
        self.assertEqual(resp, "ERR unknown_command")

    def test_ipc_server_stop_when_not_started(self) -> None:
        srv = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
        )
        # Should not raise
        srv.stop()
        self.assertFalse(srv.is_running)

    @unittest.skipUnless(os.name == "nt", "Security attributes require Windows NT")
    def test_security_attributes_creation_and_cleanup(self) -> None:
        from app.ipc.watchdog_pipe import _create_pipe_security_attributes, _free_security_descriptor
        sa, p_sd = _create_pipe_security_attributes()
        self.assertIsNotNone(sa)
        self.assertIsNotNone(p_sd)
        self.assertNotEqual(p_sd, 0)
        _free_security_descriptor(p_sd)

    def test_probe_ipc_and_recover_ok(self) -> None:
        from tools.monitor_watchdog import probe_ipc_and_recover
        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            get_status_callback=lambda: (10, 100.0, 0.02),
        )
        self.server._run = self.server._run_socket_fallback
        self.server.start()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_p = Path(tmp_dir) / "watchdog.log"
            cfg = {
                "watchdog_ipc_pipe_name": self.test_pipe,
                "watchdog_ipc_fallback_port": self.test_port,
                "watchdog_ipc_timeout_ms": 200,
            }
            outcome, detail = probe_ipc_and_recover(
                config=cfg,
                log_path=log_p,
                service_name="TestService",
                service_pid=1234,
                heartbeat_tick_sequence=9,
                heartbeat_last_tick_ts=time.time(),
                no_notify=True,
            )
            self.assertEqual(outcome, "ok")
            self.assertIsNone(detail)

    def test_probe_ipc_and_recover_deadlock(self) -> None:
        from unittest import mock
        from tools.monitor_watchdog import probe_ipc_and_recover
        # Server returns frozen tick sequence 5
        self.server = WatchdogIPCServer(
            pipe_name=self.test_pipe,
            fallback_port=self.test_port,
            timeout_s=0.2,
            get_status_callback=lambda: (5, 100.0, 0.02),
        )
        self.server._run = self.server._run_socket_fallback
        self.server.start()

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_p = Path(tmp_dir) / "watchdog.log"
            cfg = {
                "watchdog_ipc_pipe_name": self.test_pipe,
                "watchdog_ipc_fallback_port": self.test_port,
                "watchdog_ipc_timeout_ms": 200,
                "watchdog_ipc_max_deadlock_tick_age_s": 10.0,
            }
            with mock.patch("tools.monitor_watchdog.restart_service", return_value=True) as mock_restart:
                outcome, detail = probe_ipc_and_recover(
                    config=cfg,
                    log_path=log_p,
                    service_name="TestService",
                    service_pid=1234,
                    heartbeat_tick_sequence=5,
                    heartbeat_last_tick_ts=time.time() - 30.0,  # 30s ago (> 10s threshold)
                    no_notify=True,
                )
                self.assertEqual(outcome, "deadlock_recovered")
                mock_restart.assert_called_once_with("TestService")

    def test_probe_ipc_and_recover_unresponsive_process_alive(self) -> None:
        from unittest import mock
        from tools.monitor_watchdog import probe_ipc_and_recover
        # No server running -> ping will fail
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_p = Path(tmp_dir) / "watchdog.log"
            cfg = {
                "watchdog_ipc_pipe_name": rf"\\.\pipe\NonExistent_{int(time.time())}",
                "watchdog_ipc_fallback_port": 29998,
                "watchdog_ipc_timeout_ms": 50,
            }
            with (
                mock.patch("tools.monitor_watchdog.process_exists", return_value=True),
                mock.patch("tools.monitor_watchdog.restart_service", return_value=True) as mock_restart,
            ):
                outcome, detail = probe_ipc_and_recover(
                    config=cfg,
                    log_path=log_p,
                    service_name="TestService",
                    service_pid=9999,
                    no_notify=True,
                    max_retries=1,
                    retry_interval_s=0.01,
                )
                self.assertEqual(outcome, "unresponsive_restarted")
                self.assertIn("9999", detail or "")
                mock_restart.assert_called_once_with("TestService")

    def test_probe_ipc_and_recover_missing_process(self) -> None:
        from unittest import mock
        from tools.monitor_watchdog import probe_ipc_and_recover
        # No server running, and process does not exist
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_p = Path(tmp_dir) / "watchdog.log"
            cfg = {
                "watchdog_ipc_pipe_name": rf"\\.\pipe\NonExistent_{int(time.time())}",
                "watchdog_ipc_fallback_port": 29997,
                "watchdog_ipc_timeout_ms": 50,
            }
            with (
                mock.patch("tools.monitor_watchdog.process_exists", return_value=False),
                mock.patch("tools.monitor_watchdog.start_service", return_value=True) as mock_start,
            ):
                outcome, detail = probe_ipc_and_recover(
                    config=cfg,
                    log_path=log_p,
                    service_name="TestService",
                    service_pid=None,
                    no_notify=True,
                    max_retries=1,
                    retry_interval_s=0.01,
                )
                self.assertEqual(outcome, "missing_started")
                mock_start.assert_called_once_with("TestService")

    def test_restart_and_start_service_helpers(self) -> None:
        from unittest import mock
        from tools import monitor_watchdog
        completed_ok = mock.Mock(returncode=0)
        completed_err = mock.Mock(returncode=1)

        with mock.patch("subprocess.run", return_value=completed_ok):
            self.assertTrue(monitor_watchdog.restart_service("MinerAlerts"))
            self.assertTrue(monitor_watchdog.start_service("MinerAlerts"))

        with mock.patch("subprocess.run", return_value=completed_err):
            self.assertFalse(monitor_watchdog.restart_service("MinerAlerts"))
            self.assertFalse(monitor_watchdog.start_service("MinerAlerts"))


if __name__ == "__main__":
    unittest.main()
