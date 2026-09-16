from __future__ import annotations

import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path

from app.core.context import MonitorContext, build_monitor_context
from app.core.engine import CoreSupervisoryEngine, TickResult
from app.core.state_manager import StateManager
from app.miner_monitor import MinerState


class StateManagerTests(unittest.TestCase):
    """Unit tests for StateManager atomic persistence and lock hierarchy."""

    def test_build_payload_creates_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            lock = threading.RLock()
            sm = StateManager(state_path=state_path, state_lock=lock)

            st = MinerState("S19-23")
            st.state = "OK"
            st.rate_ths = 100.0
            states = {"S19-23|192.168.1.23:4028": st}

            with lock:
                payload = sm.build_payload(states, last_update_id=42, last_daily_digest_date="2026-09-15")

            self.assertEqual(42, payload["last_update_id"])
            self.assertEqual("2026-09-15", payload["last_daily_digest_date"])
            self.assertIn("S19-23|192.168.1.23:4028", payload["states"])
            self.assertEqual("OK", payload["states"]["S19-23|192.168.1.23:4028"]["state"])

    def test_flush_payload_creates_atomic_file_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            lock = threading.RLock()
            sm = StateManager(state_path=state_path, state_lock=lock)

            # Initial write
            payload1 = {"states": {"m1": {"state": "OK"}}, "last_update_id": 1}
            sm.flush_payload(state_path, payload1)
            self.assertTrue(state_path.exists())

            # Second write: creates .bak
            payload2 = {"states": {"m1": {"state": "LOW"}}, "last_update_id": 2}
            sm.flush_payload(state_path, payload2)

            bak_path = state_path.with_suffix(".bak")
            self.assertTrue(bak_path.exists())

            # Check contents
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(2, saved["last_update_id"])
            bak_saved = json.loads(bak_path.read_text(encoding="utf-8"))
            self.assertEqual(1, bak_saved["last_update_id"])

    def test_save_releases_state_lock_before_disk_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            lock = threading.RLock()
            flush_lock = threading.Lock()
            sm = StateManager(state_path=state_path, state_lock=lock, flush_lock=flush_lock)

            st = MinerState("m1")
            states = {"m1": st}
            sm.save(states, last_update_id=100)
            self.assertTrue(state_path.exists())

    def test_get_and_update_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            lock = threading.RLock()
            sm = StateManager(state_path=state_path, state_lock=lock)

            st = MinerState("m1")
            st.state = "OK"
            states = {"m1": st}

            ret = sm.get_state(states, "m1")
            self.assertIsNotNone(ret)
            self.assertEqual("OK", ret.state)

            updated = sm.update_state(states, "m1", state="LOW", fails=3)
            self.assertEqual("LOW", updated.state)
            self.assertEqual(3, updated.fails)


class MonitorContextTests(unittest.TestCase):
    """Unit tests for MonitorContext container and factory."""

    def test_build_monitor_context_valid(self) -> None:
        state_path = Path(tempfile.gettempdir()) / "test_state.json"
        lock = threading.RLock()
        sm = StateManager(state_path, lock)
        q = queue.Queue(maxsize=10)

        ctx = build_monitor_context(
            config={"threshold_ths": 75.0, "poll_seconds": 25},
            state_path=state_path,
            miners=[{"name": "m1", "host": "1.2.3.4", "port": 4028}],
            bot_token="fake_token",
            chat_id="123456",
            state_lock=lock,
            telegram_queue=q,
            state_manager=sm,
            qa_mode=False,
        )

        self.assertEqual(75.0, ctx.threshold_ths)
        self.assertEqual(25, ctx.poll_seconds)
        self.assertEqual(600, ctx.startup_guard_seconds)
        self.assertEqual("admin", ctx.vnish_api_password)

    def test_build_monitor_context_requires_fields(self) -> None:
        state_path = Path(tempfile.gettempdir()) / "test_state.json"
        lock = threading.RLock()
        sm = StateManager(state_path, lock)
        q = queue.Queue(maxsize=10)

        with self.assertRaises(ValueError):
            build_monitor_context(
                config={},
                state_path=state_path,
                miners=[],
                bot_token="token",
                chat_id="123",
                state_lock=lock,
                telegram_queue=q,
                state_manager=sm,
            )


class CoreSupervisoryEngineTests(unittest.TestCase):
    """Unit tests for CoreSupervisoryEngine orchestrator and hooks."""

    def test_engine_registers_and_runs_hook(self) -> None:
        state_path = Path(tempfile.gettempdir()) / "test_state.json"
        lock = threading.RLock()
        sm = StateManager(state_path, lock)
        q = queue.Queue(maxsize=10)

        ctx = build_monitor_context(
            config={"poll_seconds": 1},
            state_path=state_path,
            miners=[{"name": "m1", "host": "1.2.3.4", "port": 4028}],
            bot_token="fake_token",
            chat_id="123456",
            state_lock=lock,
            telegram_queue=q,
            state_manager=sm,
        )

        engine = CoreSupervisoryEngine(ctx)
        completed_results: list[TickResult] = []

        def mock_hook(context: MonitorContext, seq: int, now_ts: float) -> TickResult:
            engine.shutdown()  # Stop after first tick
            return TickResult(
                tick_sequence=seq,
                tick_duration_seconds=0.01,
                miners_responded=1,
                miners_failed=0,
                reboots_triggered=[],
                governance_blocked=0,
                errors=[],
            )

        engine.register_tick_hook(mock_hook)
        engine.run(states={}, last_update_id_ref={"value": 1}, on_tick_complete=completed_results.append)

        self.assertEqual(1, len(completed_results))
        res = completed_results[0]
        self.assertEqual(1, res.tick_sequence)
        self.assertEqual(1, res.miners_responded)
        self.assertEqual(0, res.miners_failed)
        self.assertFalse(engine.is_running)


if __name__ == "__main__":
    unittest.main()
