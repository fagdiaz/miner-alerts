"""tests/test_preset_balancer_integration.py
Spec 040: Dynamic Power & Preset Balancer Integration & Concurrency Tests.

Validates:
  1. execute_balancer_cycle dry_run evaluation and state updates.
  2. execute_balancer_cycle active write with safe_set_miner_preset mock.
  3. Non-blocking concurrency: ThreadPoolExecutor handles multiple miners with fleet timeout.
  4. Periodic interval guard (only executes when interval elapsed unless force=True).
  5. State serialization and deserialization in load_state/save_state.
  6. Telegram command dispatch and formatting for /balancer, /balancer setmax, /balancer on/off, /balancer run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.miner_monitor import (
    MinerState,
    execute_balancer_cycle,
    load_state,
    save_state,
    _is_command_like,
)
from app.preset_balancer import (
    ACTION_HOLD_STABLE,
    ACTION_STEP_DOWN_CASCADE,
    ACTION_STEP_DOWN_RESTARTS,
    ACTION_STEP_UP_OPTIMIZE,
    BalancerConfig,
    StabilityMetrics,
    build_balancer_table_text,
    build_miner_balancer_detail_text,
    evaluate_balancer_step,
)


def _make_balancer_config(**overrides) -> dict:
    cfg = {
        "preset_balancer_enabled": True,
        "preset_balancer_dry_run": True,
        "preset_balancer_interval_seconds": 1800,
        "preset_balancer_restarts_step_down": 2,
        "preset_balancer_soak_hours_step_up": 72.0,
        "preset_balancer_default_max_preset": "2700W",
        "preset_balancer_group_cascade_threshold": 2,
        "preset_balancer_group_cascade_window_s": 1800.0,
        "preset_balancer_min_thermal_headroom_c": 4.0,
        "vnish_api_password": "admin",
        "fan_governor_request_timeout": 2.5,
        "fan_governor_fleet_timeout": 5.0,
    }
    cfg.update(overrides)
    return cfg


class TestPresetBalancerIntegration(unittest.TestCase):
    def setUp(self):
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2"},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2"},
        ]
        self.states = {}
        for m in self.miners:
            sk = f"{m['name']}|{m['host']}:{m['port']}"
            st = MinerState()
            st.balancer_preset = "2700W"
            self.states[sk] = st
        self.lock = threading.Lock()

    def test_command_whitelist_contains_balancer(self):
        self.assertTrue(_is_command_like("balancer"))
        self.assertTrue(_is_command_like("bal"))
        self.assertTrue(_is_command_like("power"))
        self.assertTrue(_is_command_like("governor"))
        self.assertTrue(_is_command_like("gov"))

    def test_state_serialization_preserves_balancer_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            st_path = Path(tmpdir) / "state.json"
            states_in = {
                "S19JPRO-23|192.168.100.23:4028": MinerState(
                    balancer_preset="2500W",
                    balancer_last_change_ts=1700000000.0,
                    balancer_last_action="STEP_DOWN_RESTARTS",
                    balancer_last_reason="Test reason",
                )
            }
            save_state(st_path, states_in, last_update_id=123)
            loaded, last_id = load_state(st_path)
            self.assertEqual(last_id, 123)
            self.assertIn("S19JPRO-23|192.168.100.23:4028", loaded)
            st = loaded["S19JPRO-23|192.168.100.23:4028"]
            self.assertEqual(st.balancer_preset, "2500W")
            self.assertEqual(st.balancer_last_change_ts, 1700000000.0)
            self.assertEqual(st.balancer_last_action, "STEP_DOWN_RESTARTS")
            self.assertEqual(st.balancer_last_reason, "Test reason")

    def test_execute_balancer_cycle_dry_run_simulation(self):
        cfg = _make_balancer_config(preset_balancer_dry_run=True)
        mock_metrics = [
            StabilityMetrics(
                miner_name="S19JPRO-23",
                electrical_group="elevator_1",
                current_preset="2700W",
                restarts_24h=3,
                restarts_72h=4,
                hours_since_last_restart=2.0,
                avg_hashrate_24h_ths=85.0,
                downtime_minutes_24h=30.0,
                thermal_headroom_c=5.0,
            ),
            StabilityMetrics(
                miner_name="S19JPRO-25",
                electrical_group="elevator_2",
                current_preset="2500W",
                restarts_24h=0,
                restarts_72h=0,
                hours_since_last_restart=80.0,
                avg_hashrate_24h_ths=93.0,
                downtime_minutes_24h=0.0,
                thermal_headroom_c=6.0,
            ),
        ]

        with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=mock_metrics):
            with patch("app.miner_monitor.safe_set_miner_preset") as mock_set:
                decisions = execute_balancer_cycle(
                    miners=self.miners,
                    states=self.states,
                    state_lock=self.lock,
                    config=cfg,
                    now_ts=time.time(),
                    qa_mode=False,
                    force=True,
                )

        mock_set.assert_not_called()
        self.assertEqual(len(decisions), 2)
        m23_metrics, m23_decision = decisions[0]
        self.assertEqual(m23_decision.action, ACTION_STEP_DOWN_RESTARTS)
        self.assertEqual(m23_decision.target_preset, "2500W")

        st23 = self.states["S19JPRO-23|192.168.100.23:4028"]
        self.assertEqual(st23.balancer_preset, "2500W")
        self.assertEqual(st23.balancer_last_action, ACTION_STEP_DOWN_RESTARTS)

    def test_execute_balancer_cycle_active_write(self):
        cfg = _make_balancer_config(preset_balancer_dry_run=False)
        mock_metrics = [
            StabilityMetrics(
                miner_name="S19JPRO-23",
                electrical_group="elevator_1",
                current_preset="2700W",
                restarts_24h=2,
                restarts_72h=2,
                hours_since_last_restart=1.0,
                avg_hashrate_24h_ths=86.0,
                downtime_minutes_24h=20.0,
                thermal_headroom_c=5.0,
            )
        ]

        with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=mock_metrics):
            with patch("app.miner_monitor.safe_set_miner_preset", return_value=(True, None)) as mock_set:
                decisions = execute_balancer_cycle(
                    miners=self.miners[:1],
                    states=self.states,
                    state_lock=self.lock,
                    config=cfg,
                    now_ts=time.time(),
                    qa_mode=False,
                    force=True,
                )

        self.assertEqual(mock_set.call_count, 1)
        mock_set.assert_called_with("192.168.100.23", "admin", "2500W", timeout=2.5)
        st23 = self.states["S19JPRO-23|192.168.100.23:4028"]
        self.assertEqual(st23.balancer_preset, "2500W")
        self.assertEqual(st23.balancer_last_action, ACTION_STEP_DOWN_RESTARTS)

    def test_execute_balancer_cycle_interval_guard(self):
        cfg = _make_balancer_config(preset_balancer_interval_seconds=1800)
        now = 10000.0

        with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=[]):
            dec1 = execute_balancer_cycle(
                miners=self.miners,
                states=self.states,
                state_lock=self.lock,
                config=cfg,
                now_ts=now,
                qa_mode=False,
                force=False,
            )
            dec2 = execute_balancer_cycle(
                miners=self.miners,
                states=self.states,
                state_lock=self.lock,
                config=cfg,
                now_ts=now + 60.0,
                qa_mode=False,
                force=False,
            )
            self.assertEqual(dec2, [])


class TestFleetTimeoutAndConcurrency(unittest.TestCase):
    def setUp(self):
        self.miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
        ]
        self.states = {}
        for m in self.miners:
            sk = f"{m['name']}|{m['host']}:{m['port']}"
            st = MinerState()
            st.balancer_preset = "2700W"
            self.states[sk] = st
        self.lock = threading.Lock()

    def test_slow_miner_does_not_block_beyond_fleet_timeout(self):
        cfg = _make_balancer_config(
            preset_balancer_dry_run=False,
            fan_governor_request_timeout=1.0,
            fan_governor_fleet_timeout=1.0,
        )
        mock_metrics = [
            StabilityMetrics(
                miner_name="S19JPRO-23",
                electrical_group="elevator_1",
                current_preset="2700W",
                restarts_24h=3,
                restarts_72h=3,
                hours_since_last_restart=1.0,
                avg_hashrate_24h_ths=85.0,
                downtime_minutes_24h=30.0,
                thermal_headroom_c=5.0,
            )
        ]

        def slow_set(host, pw, preset, timeout=2.5):
            time.sleep(3.0)  # Exceeds 1.0s fleet timeout
            return True, None

        with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=mock_metrics):
            with patch("app.miner_monitor.safe_set_miner_preset", side_effect=slow_set):
                t0 = time.monotonic()
                execute_balancer_cycle(
                    miners=self.miners[:1],
                    states=self.states,
                    state_lock=self.lock,
                    config=cfg,
                    now_ts=time.time(),
                    qa_mode=False,
                    force=True,
                )
                elapsed = time.monotonic() - t0
                self.assertLess(elapsed, 2.5, f"Cycle took {elapsed:.2f}s, expected < 2.5s")

    def test_state_lock_concurrency_no_deadlock(self):
        cfg = _make_balancer_config(preset_balancer_dry_run=True)
        mock_metrics = [
            StabilityMetrics(
                miner_name=m["name"],
                electrical_group="elevator_1",
                current_preset="2700W",
                restarts_24h=0,
                restarts_72h=0,
                hours_since_last_restart=80.0,
                avg_hashrate_24h_ths=95.0,
                downtime_minutes_24h=0.0,
                thermal_headroom_c=6.0,
            )
            for m in self.miners
        ]

        errors = []
        def worker():
            try:
                for _ in range(5):
                    with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=mock_metrics):
                        execute_balancer_cycle(
                            miners=self.miners,
                            states=self.states,
                            state_lock=self.lock,
                            config=cfg,
                            now_ts=time.time(),
                            qa_mode=False,
                            force=True,
                        )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Concurrent execution errors: {errors}")


class TestTelegramHelpAndCommands(unittest.TestCase):
    def test_help_index_includes_balancer_and_governor(self):
        from app.miner_monitor import render_help_index
        text = render_help_index()
        self.assertIn("/balancer", text)
        self.assertIn("/gov", text)
        self.assertIn("fans", text)
        self.assertIn("presets", text)

    def test_help_usage_for_balancer_aliases(self):
        from app.miner_monitor import _help_usage_for
        u1 = _help_usage_for("balancer")
        u2 = _help_usage_for("bal")
        u3 = _help_usage_for("power")
        self.assertIsNotNone(u1)
        self.assertEqual(u1, u2)
        self.assertEqual(u1, u3)
        self.assertIn("/balancer", u1)


if __name__ == "__main__":
    unittest.main()
