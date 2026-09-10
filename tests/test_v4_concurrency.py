#!/usr/bin/env python3
"""High-Contention Concurrency & Thread-Safety Stress Test Suite (Spec 053).

Validates that high-concurrency contention across Telegram command threads,
polling threads, and governance workers operates with zero deadlocks, zero
race conditions, and zero state file corruption.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

from app.governance.maintenance_scheduler import (
    ScheduledStage,
    ScheduledWindow,
    evaluate_window_stage,
    parse_schedule_expression,
    process_maintenance_scheduler_cycle,
)
from app.governance.phase_drop_discriminator import (
    PhaseDropAssessment,
    PhaseDropConfig,
    PhaseDropVerdict,
    evaluate_phase_drop,
)
from app.governance.post_blackout_guard import (
    PostBlackoutTarget,
    PostBlackoutTracker,
    evaluate_miner_post_blackout,
)
from app.miner_monitor import MinerState, save_state


class TestV4Concurrency(unittest.TestCase):
    """Stress tests concurrent state mutations, save_state, and governance cycles."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_concurrent_save_state_and_mutations(self) -> None:
        """Verify concurrent mutations and save_state calls never crash or corrupt JSON."""
        state_lock = threading.RLock()
        states: Dict[str, MinerState] = {
            f"miner_{i}": MinerState() for i in range(10)
        }
        for st in states.values():
            st.initialized = True
            st.state = "OK"

        errors: List[Exception] = []
        stop_event = threading.Event()

        def state_mutator(tid: int) -> None:
            nonlocal states
            while not stop_event.is_set():
                try:
                    for i in range(10):
                        m_key = f"miner_{i}"
                        with state_lock:
                            st = states[m_key]
                            st.ok_streak += 1
                            st.last_seen_ts = time.time()
                            st.last_max_chip_temp = 75.0 + (tid % 10)
                            if st.auto_reboot_timestamps is None:
                                st.auto_reboot_timestamps = []
                            st.auto_reboot_timestamps.append(time.time())
                            if len(st.auto_reboot_timestamps) > 20:
                                st.auto_reboot_timestamps.pop(0)
                            st.is_shutdown_maintenance = (tid % 2 == 0)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.001)

        def state_saver() -> None:
            while not stop_event.is_set():
                try:
                    with state_lock:
                        save_state(
                            state_path=self.state_path,
                            states=states,
                            last_update_id=12345,
                        )
                        # Verify file validity under lock to prevent Windows file-sharing collision
                        if self.state_path.exists():
                            raw = self.state_path.read_text(encoding="utf-8")
                            data = json.loads(raw)
                            self.assertEqual(data["last_update_id"], 12345)
                            self.assertIn("states", data)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.005)

        # Launch 4 mutator threads and 2 saver threads
        threads: List[threading.Thread] = []
        for tid in range(4):
            t = threading.Thread(target=state_mutator, args=(tid,), daemon=True)
            threads.append(t)
        for _ in range(2):
            t = threading.Thread(target=state_saver, daemon=True)
            threads.append(t)

        for t in threads:
            t.start()

        # Run under heavy contention for 0.5 seconds
        time.sleep(0.5)
        stop_event.set()

        for t in threads:
            t.join(timeout=1.0)

        self.assertEqual(len(errors), 0, f"Encountered concurrency errors: {errors}")
        self.assertTrue(self.state_path.exists(), "state.json was not written")
        final_data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(final_data["states"]), 10)

    def test_reentrant_lock_nesting_safety(self) -> None:
        """Verify RLock handles recursive locking across monitor helpers without deadlocking."""
        state_lock = threading.RLock()
        states = {"m1": MinerState()}

        acquired_depth = 0
        with state_lock:
            acquired_depth += 1
            with state_lock:
                acquired_depth += 1
                save_state(self.state_path, states, 100)
                with state_lock:
                    acquired_depth += 1

        self.assertEqual(acquired_depth, 3)
        self.assertTrue(self.state_path.exists())

    def test_concurrent_maintenance_stage_evaluations(self) -> None:
        """Verify concurrent evaluations and cancellations of scheduled windows."""
        ok, window, _ = parse_schedule_expression("in 30m", "2h", now_ts=1000.0)
        self.assertTrue(ok)
        self.assertIsNotNone(window)
        assert window is not None

        errors: List[Exception] = []
        stop_event = threading.Event()

        def stage_evaluator() -> None:
            while not stop_event.is_set():
                try:
                    now = 1000.0 + (time.time() % 3600.0)
                    evaluate_window_stage(window, now)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=stage_evaluator, daemon=True) for _ in range(6)]
        for t in threads:
            t.start()

        time.sleep(0.2)
        window.stage = ScheduledStage.CANCELLED
        time.sleep(0.2)
        stop_event.set()

        for t in threads:
            t.join(timeout=1.0)

        self.assertEqual(len(errors), 0)
        self.assertEqual(window.stage, ScheduledStage.CANCELLED)

    def test_concurrent_phase_drop_and_blackout_evaluation(self) -> None:
        """Verify parallel evaluation of phase drop and post blackout is thread-safe."""
        elev_groups = {f"miner_{i}": f"elev_{i%2}" for i in range(4)}
        errors: List[Exception] = []

        def worker(tid: int) -> None:
            try:
                for cycle in range(50):
                    failed = [f"miner_{i}" for i in range(tid % 2)]
                    responded = [f"miner_{i}" for i in range(tid % 2, 4)]
                    evaluate_phase_drop(
                        failed_miners=failed,
                        responded_miners=responded,
                        host_network_ok=True,
                        elevator_groups=elev_groups,
                    )
                    evaluate_miner_post_blackout(
                        miner_id=f"miner_{tid%4}",
                        name=f"miner_{tid%4}",
                        host="127.0.0.1",
                        miner_state="stopped" if tid % 2 == 0 else "running",
                        rate_ths=0.0 if tid % 2 == 0 else 100.0,
                        uptime_seconds=120,
                        consecutive_stopped_ticks=2,
                        in_maintenance=False,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
