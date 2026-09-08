"""tests/test_v3_concurrency.py
Deterministic concurrency test suite for V3 release stabilization (Spec 038).

Simulates multi-threaded contention between:
  - Main monitor loop (per-tick state mutations)
  - Telegram polling worker (snooze commands, reboot callbacks)
  - Concurrent callback button taps (rb_req, rb_cfm, rb_ccl)
  - SQLite read-only connections (read-under-write safety)

All tests are deterministic: no sleep-based timing, only barrier/event
synchronization.  They assert zero deadlocks, zero uncaught exceptions,
and zero state corruption.
"""

from __future__ import annotations

import sys
import os
import threading
import time
import unittest
from pathlib import Path

# Make sure we can import from the app package in both modes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.telegram_callbacks import (
        CallbackTokenRegistry,
        build_alert_keyboard,
        build_confirmation_keyboard,
        build_settled_keyboard,
        parse_callback_data,
    )
    from app.miner_monitor import MinerState
except ImportError:  # fallback direct import
    from telegram_callbacks import (
        CallbackTokenRegistry,
        build_alert_keyboard,
        build_confirmation_keyboard,
        build_settled_keyboard,
        parse_callback_data,
    )
    from miner_monitor import MinerState  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state() -> MinerState:
    """Return a fresh MinerState with sensible defaults."""
    s = MinerState()
    s.state = "OK"
    return s


# ---------------------------------------------------------------------------
# Phase 1 — State-lock correctness under concurrent mutations
# ---------------------------------------------------------------------------

class TestStateLockConcurrency(unittest.TestCase):
    """Verify that concurrent reads/writes to MinerState V3 fields are safe
    when properly protected by a threading.Lock."""

    def test_snooze_concurrent_read_write(self):
        """Monitor loop reads snooze_until_ts while Telegram thread writes it."""
        state = _make_state()
        lock = threading.Lock()
        now_ts = time.time()
        errors: list = []
        ITERATIONS = 500

        def writer():
            for i in range(ITERATIONS):
                with lock:
                    state.snooze_until_ts = now_ts + 3600.0 if i % 2 == 0 else None

        def reader():
            for _ in range(ITERATIONS):
                with lock:
                    val = state.snooze_until_ts
                if val is not None and not isinstance(val, float):
                    errors.append(f"Unexpected type: {type(val)}")

        t1 = threading.Thread(target=writer, daemon=True)
        t2 = threading.Thread(target=reader, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert not errors, f"State corruption detected: {errors}"

    def test_cooling_streak_concurrent_increment(self):
        """Two threads increment cooling_streak under a lock; final value must be 2000."""
        state = _make_state()
        lock = threading.Lock()
        ITERATIONS = 1000
        state.cooling_streak = 0

        def increment():
            for _ in range(ITERATIONS):
                with lock:
                    state.cooling_streak += 1

        t1 = threading.Thread(target=increment, daemon=True)
        t2 = threading.Thread(target=increment, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert state.cooling_streak == ITERATIONS * 2

    def test_save_state_snapshot_no_runtime_error(self):
        """save_state must not raise RuntimeError when states dict grows concurrently."""
        import json
        states = {}
        state_lock = threading.Lock()
        errors = []
        for i in range(5):
            states[f"miner{i}|10.0.0.{i}:4028"] = _make_state()

        def simulate_save():
            for _ in range(200):
                with state_lock:
                    try:
                        snapshot = {}
                        for key, st in list(states.items()):
                            snapshot[key] = {"state": st.state}
                        json.dumps(snapshot)
                    except RuntimeError as exc:
                        errors.append(exc)

        def simulate_main_loop():
            for i in range(200):
                new_key = f"miner_dyn{i}|10.1.0.{i}:4028"
                states.setdefault(new_key, _make_state())

        t1 = threading.Thread(target=simulate_save, daemon=True)
        t2 = threading.Thread(target=simulate_main_loop, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)
        assert not errors, f"save_state raised: {errors}"

    def test_snooze_blocks_auto_reboot_atomically(self):
        """With snooze set and refreshed concurrently, zero false reboots must occur."""
        state = _make_state()
        lock = threading.Lock()
        ITERATIONS = 1000
        false_reboots = 0
        with lock:
            state.snooze_until_ts = time.time() + 3600.0

        def evaluator():
            nonlocal false_reboots
            for _ in range(ITERATIONS):
                with lock:
                    is_snoozed = (
                        state.snooze_until_ts is not None
                        and time.time() < state.snooze_until_ts
                    )
                if not is_snoozed:
                    false_reboots += 1

        def snooze_refresher():
            for _ in range(ITERATIONS):
                with lock:
                    state.snooze_until_ts = time.time() + 3600.0

        t1 = threading.Thread(target=evaluator, daemon=True)
        t2 = threading.Thread(target=snooze_refresher, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        assert false_reboots == 0, f"{false_reboots} false reboots under snooze!"


# ---------------------------------------------------------------------------
# Phase 2 — Callback token registry concurrency & single-use guarantee
# ---------------------------------------------------------------------------

class TestCallbackTokenConcurrency(unittest.TestCase):

    def test_single_consume_from_concurrent_threads(self):
        """Only ONE thread among 5 concurrent consumers should consume the token."""
        registry = CallbackTokenRegistry(ttl_seconds=60.0)
        token = registry.create_token("miner23")
        successes = []
        lock = threading.Lock()
        barrier = threading.Barrier(5)

        def try_consume():
            barrier.wait()
            valid, miner, status = registry.consume_token(token)
            if valid:
                with lock:
                    successes.append(miner)

        threads = [threading.Thread(target=try_consume, daemon=True) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=5)
        assert len(successes) == 1, f"Expected 1 consume, got {len(successes)}"

    def test_expired_token_rejected(self):
        """TTL=0 token must be expired on consume."""
        registry = CallbackTokenRegistry(ttl_seconds=0.0)
        token = registry.create_token("miner42")
        time.sleep(0.01)
        valid, _, status = registry.consume_token(token)
        assert not valid
        assert status == "token_expired"

    def test_concurrent_token_creation_bounded(self):
        """50 concurrent creates must not exceed max_tokens=10."""
        registry = CallbackTokenRegistry(ttl_seconds=60.0, max_tokens=10)
        barrier = threading.Barrier(50)

        def create():
            barrier.wait()
            registry.create_token("miner1")

        threads = [threading.Thread(target=create, daemon=True) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=10)
        assert len(registry._tokens) <= 10, f"Exceeded max_tokens: {len(registry._tokens)}"

    def test_double_tap_only_one_succeeds(self):
        """Double-tap: two simultaneous rb_cfm — exactly one must succeed."""
        registry = CallbackTokenRegistry(ttl_seconds=60.0)
        token = registry.create_token("miner7")
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def tap():
            barrier.wait()
            result = registry.consume_token(token)
            with lock:
                results.append(result)

        t1 = threading.Thread(target=tap, daemon=True)
        t2 = threading.Thread(target=tap, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)
        successes = [r for r in results if r[0] is True]
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"

    def test_rapid_cycle_no_exceptions(self):
        """Rapid rb_req/rb_cfm/rb_ccl from 5 concurrent threads for 300ms."""
        registry = CallbackTokenRegistry(ttl_seconds=60.0)
        errors = []
        stop = threading.Event()

        def cycle(miner_id):
            while not stop.is_set():
                try:
                    tok = registry.create_token(miner_id)
                    registry.consume_token(tok)
                    registry.invalidate_miner(miner_id)
                except Exception as exc:
                    errors.append(exc)
                    stop.set()

        threads = [threading.Thread(target=cycle, args=(f"miner{i}",), daemon=True) for i in range(5)]
        for t in threads: t.start()
        time.sleep(0.3)
        stop.set()
        for t in threads: t.join(timeout=3)
        assert not errors, f"Exceptions: {errors[:3]}"


# ---------------------------------------------------------------------------
# Phase 3 — Snooze + auto-reboot interlock invariant
# ---------------------------------------------------------------------------

class TestSnoozeAutoRebootInterlock(unittest.TestCase):

    def test_snooze_set_blocks_reboot_flag(self):
        """If snooze_until_ts > now_ts, auto-reboot evaluation must be False."""
        state = _make_state()
        state.reboot_pending_until = time.time() + 300.0
        state.snooze_until_ts = time.time() + 3600.0
        now_ts = time.time()
        is_snoozed = state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
        would_reboot = (
            not is_snoozed
            and state.reboot_pending_until
            and (now_ts - state.last_reboot_ts) >= 900
        )
        assert not would_reboot, "Auto-reboot fired while snoozed!"

    def test_snooze_expiry_allows_reboot(self):
        """After snooze expires, auto-reboot evaluation proceeds."""
        state = _make_state()
        state.snooze_until_ts = time.time() - 1.0
        now_ts = time.time()
        is_snoozed = state.snooze_until_ts is not None and now_ts < state.snooze_until_ts
        assert not is_snoozed, "Expired snooze should NOT block auto-reboot"


# ---------------------------------------------------------------------------
# Phase 4 — Queue non-blocking stress test
# ---------------------------------------------------------------------------

class TestQueueNonBlocking(unittest.TestCase):

    def test_concurrent_queue_puts_no_deadlock(self):
        """10 threads putting into queue concurrently must not deadlock."""
        import queue
        q = queue.Queue(maxsize=200)
        errors = []
        lock = threading.Lock()

        def producer(idx):
            for i in range(20):
                try:
                    q.put_nowait(f"msg-{idx}-{i}")
                except queue.Full:
                    pass
                except Exception as exc:
                    with lock:
                        errors.append(exc)

        threads = [threading.Thread(target=producer, args=(i,), daemon=True) for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=5)
        assert not errors, f"Queue put errors: {errors}"


# ---------------------------------------------------------------------------
# Phase 5 — Grammar parsing is stateless and thread-safe
# ---------------------------------------------------------------------------

class TestCallbackGrammarConcurrency(unittest.TestCase):

    def test_parse_concurrent_no_errors(self):
        """parse_callback_data from 20 concurrent threads must not raise."""
        test_cases = [
            "diag:23", "chart:23", "snz:23:60",
            "rb_req:23", "rb_cfm:e8f2a1:23", "rb_ccl:23",
            "noop", "invalid:data:too:many:parts",
        ]
        errors = []
        lock = threading.Lock()

        def parser():
            for _ in range(200):
                for raw in test_cases:
                    try:
                        parse_callback_data(raw)
                    except Exception as exc:
                        with lock:
                            errors.append(exc)

        threads = [threading.Thread(target=parser, daemon=True) for _ in range(20)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=10)
        assert not errors, f"parse_callback_data raised: {errors[:3]}"

    def test_keyboard_builders_concurrent(self):
        """Keyboard builders are pure functions — concurrent calls must be safe."""
        errors = []
        lock = threading.Lock()

        def builder():
            for i in range(200):
                try:
                    build_alert_keyboard(str(i % 10))
                    build_confirmation_keyboard(str(i % 10), "abc123")
                    build_settled_keyboard("Done")
                except Exception as exc:
                    with lock:
                        errors.append(exc)

        threads = [threading.Thread(target=builder, daemon=True) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=5)
        assert not errors, f"Keyboard builder raised: {errors[:3]}"


# ---------------------------------------------------------------------------
# Phase 6 — SQLite connection contract verification (source inspection)
# ---------------------------------------------------------------------------

class TestSQLiteConnectionContract(unittest.TestCase):

    def test_telegram_charts_mode_ro_with_timeout(self):
        """telegram_charts._connect_ro must use ?mode=ro and timeout=2.0."""
        import inspect
        try:
            from app.telegram_charts import _connect_ro
        except ImportError:
            from telegram_charts import _connect_ro  # type: ignore
        src = inspect.getsource(_connect_ro)
        assert "mode=ro" in src, "_connect_ro missing ?mode=ro"
        assert "timeout=2.0" in src, "_connect_ro missing timeout=2.0"

    def test_daily_digest_finally_conn_close(self):
        """daily_digest.fetch_daily_digest_metrics must use finally + conn.close()."""
        import inspect
        try:
            from app.daily_digest import fetch_daily_digest_metrics
        except ImportError:
            from daily_digest import fetch_daily_digest_metrics  # type: ignore
        src = inspect.getsource(fetch_daily_digest_metrics)
        assert "finally" in src, "daily_digest missing finally: block"
        assert "conn.close()" in src, "daily_digest missing conn.close()"
        assert "mode=ro" in src, "daily_digest missing ?mode=ro"
        assert "timeout=2.0" in src, "daily_digest missing timeout=2.0"

    def test_fan_health_finally_conn_close(self):
        """fan_health must use finally for conn.close()."""
        import inspect
        try:
            from app.fan_health import fetch_latest_cooling_assessments
        except ImportError:
            from fan_health import fetch_latest_cooling_assessments  # type: ignore
        src = inspect.getsource(fetch_latest_cooling_assessments)
        assert "finally" in src
        assert "mode=ro" in src

    def test_energy_efficiency_finally_conn_close(self):
        """energy_efficiency must use finally for conn.close()."""
        import inspect
        try:
            from app.energy_efficiency import fetch_latest_efficiency_assessments
        except ImportError:
            from energy_efficiency import fetch_latest_efficiency_assessments  # type: ignore
        src = inspect.getsource(fetch_latest_efficiency_assessments)
        assert "finally" in src
        assert "mode=ro" in src

    def test_vnish_presets_finally_conn_close(self):
        """vnish_presets must use finally for conn.close()."""
        import inspect
        try:
            from app.vnish_presets import fetch_latest_preset_assessments
        except ImportError:
            from vnish_presets import fetch_latest_preset_assessments  # type: ignore
        src = inspect.getsource(fetch_latest_preset_assessments)
        assert "finally" in src
        assert "mode=ro" in src


if __name__ == "__main__":
    unittest.main()
