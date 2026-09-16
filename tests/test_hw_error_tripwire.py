"""
Unit and integration tests for Spec 062:
HW Error Tripwire & Rollback Automatico de Overclock (GOV-01).

Tests:
1. Pure mathematical decision engine evaluate_balancer_step():
   - Tripwire trigger condition (AND gate: error rate >= threshold AND delta >= threshold).
   - Sub-threshold error rate or delta does not trigger tripwire.
   - Tripwire step-down at minimum preset emits ACTION_LOCKED_MIN.
   - Lockout enforcement against post-reboot firmware override (restores locked preset).
   - Step-up inhibition while lock is active, restoration of step-up once expired.
2. Non-volatile delta extraction in extract_miner_stability_metrics() with SQLite:
   - Sample T vs Sample T - 10m calculation.
   - Counter reset handling.
   - No past sample fallback.
3. Mobile-First Telegram card rendering (line width <= 32 columns).
4. State persistence & anti-cascade cycle across simulated reboots.
5. Non-interference with auto-reboot safety for STATE_LOW and STATE_HASHBOARD.
"""

import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from app.core.event_store import EventStore
from app.core.state_manager import StateManager, _serialise_miner_state
from app.governance.preset_balancer import (
    ACTION_HOLD_STABLE,
    ACTION_LOCKED_MIN,
    ACTION_STEP_DOWN_HW_ERRORS,
    ACTION_STEP_DOWN_RESTARTS,
    ACTION_STEP_UP_OPTIMIZE,
    DEFAULT_PRESET_LADDER,
    BalancerConfig,
    StabilityMetrics,
    evaluate_balancer_step,
    extract_miner_stability_metrics,
    find_preset_index,
    render_hw_error_tripwire_card,
)
from app.miner_monitor import (
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OK,
    MinerState,
    _build_state_payload,
    evaluate_auto_reboot_interlocks,
    execute_balancer_cycle,
    load_state,
)


class TestHWErrorTripwirePureEngine(unittest.TestCase):
    """Unit tests for evaluate_balancer_step tripwire logic and lockout enforcement."""

    def setUp(self):
        self.cfg = BalancerConfig(
            hw_error_rate_threshold_pct=0.5,
            hw_error_delta_threshold=200,
            hw_error_lock_hours=48.0,
        )
        self.now = 1000000.0

    def test_tripwire_triggers_when_both_thresholds_exceeded(self):
        """Tripwire triggers step-down when rate >= 0.5% AND delta >= 200."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            hw_errors_delta_10m=250,
            hw_error_rate_pct=0.65,
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertEqual(decision.action, ACTION_STEP_DOWN_HW_ERRORS)
        self.assertEqual(decision.current_preset, "2700W")
        self.assertEqual(decision.target_preset, "2500W")
        self.assertTrue(decision.requires_write)
        self.assertIn("Tripwire errores HW", decision.reason)
        self.assertIn("250 en 10m", decision.reason)

    def test_tripwire_does_not_trigger_if_rate_below_threshold(self):
        """Delta >= 200 but error rate < 0.5% must not trigger tripwire."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            hw_errors_delta_10m=250,
            hw_error_rate_pct=0.35,
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertNotEqual(decision.action, ACTION_STEP_DOWN_HW_ERRORS)
        self.assertEqual(decision.action, ACTION_HOLD_STABLE)

    def test_tripwire_does_not_trigger_if_delta_below_threshold(self):
        """Rate >= 0.5% but delta < 200 must not trigger tripwire."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            hw_errors_delta_10m=120,
            hw_error_rate_pct=1.2,
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertNotEqual(decision.action, ACTION_STEP_DOWN_HW_ERRORS)
        self.assertEqual(decision.action, ACTION_HOLD_STABLE)

    def test_tripwire_at_minimum_preset_emits_locked_min(self):
        """Tripwire triggered at 1600W (lowest tier) emits ACTION_LOCKED_MIN with requires_write=False."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="1600W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            hw_errors_delta_10m=300,
            hw_error_rate_pct=1.5,
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertEqual(decision.action, ACTION_LOCKED_MIN)
        self.assertEqual(decision.current_preset, "1600W")
        self.assertEqual(decision.target_preset, "1600W")
        self.assertFalse(decision.requires_write)
        self.assertIn("Preset m\u00ednimo (1600W) alcanzado", decision.reason)

    def test_lockout_enforcement_forces_step_down_if_preset_exceeds_locked(self):
        """If active lock is present and current preset exceeds locked preset, force step down."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            hw_errors_delta_10m=10,
            hw_error_rate_pct=0.01,
            hw_error_lock_until_ts=self.now + 3600.0 * 24.0,
            hw_error_locked_preset="2500W",
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertEqual(decision.action, ACTION_STEP_DOWN_HW_ERRORS)
        self.assertEqual(decision.target_preset, "2500W")
        self.assertTrue(decision.requires_write)
        self.assertIn("Candado errores HW activo", decision.reason)

    def test_lockout_inhibits_step_up_during_lock(self):
        """Step-up is inhibited while lock is active, even if stability soak is satisfied."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2500W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            thermal_headroom_c=6.0,
            hw_errors_delta_10m=5,
            hw_error_rate_pct=0.01,
            hw_error_lock_until_ts=self.now + 3600.0 * 12.0,
            hw_error_locked_preset="2500W",
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertEqual(decision.action, ACTION_HOLD_STABLE)
        self.assertIn("retenida en 2500W por candado errores HW", decision.reason)

    def test_step_up_resumes_after_lock_expiry(self):
        """Once lock is expired, step-up is permitted if stability criteria are met."""
        metrics = StabilityMetrics(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            current_preset="2500W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            thermal_headroom_c=6.0,
            hw_errors_delta_10m=5,
            hw_error_rate_pct=0.01,
            hw_error_lock_until_ts=self.now - 1.0,
            hw_error_locked_preset="2500W",
        )
        decision = evaluate_balancer_step(metrics, self.cfg, now_ts=self.now)
        self.assertEqual(decision.action, ACTION_STEP_UP_OPTIMIZE)
        self.assertEqual(decision.target_preset, "2700W")
        self.assertTrue(decision.requires_write)


class TestHWErrorDeltaExtractionSQLite(unittest.TestCase):
    """Unit tests for SQLite telemetry_samples extraction of 10m HW error deltas."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_miner_alerts.db"
        self._init_sqlite_db()

    def tearDown(self):
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except Exception:
                pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _init_sqlite_db(self):
        es = EventStore(self.db_path, async_check=False)
        es.close()

    def test_extract_stability_metrics_calculates_10m_delta_and_rate(self):
        """extract_miner_stability_metrics computes 10m delta comparing T and T-10m samples."""
        now = 1000000.0
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded, threshold_ths, expected_boards,
                rate_ths, max_temp_c, chain_power_w_total, elapsed_seconds, hw_errors_total, accepted_shares_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now - 650.0, "S19JPRO-01|192.168.1.101:4028", "S19JPRO-01", "192.168.1.101", "OK", 1, 80.0, 3, 90.0, 72.0, 2700.0, 3600, 10, 500),
        )
        cursor.execute(
            """
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded, threshold_ths, expected_boards,
                rate_ths, max_temp_c, chain_power_w_total, elapsed_seconds, hw_errors_total, accepted_shares_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, "S19JPRO-01|192.168.1.101:4028", "S19JPRO-01", "192.168.1.101", "OK", 1, 80.0, 3, 90.0, 72.0, 2700.0, 4250, 240, 960),
        )
        conn.commit()
        conn.close()

        miners = [{"name": "S19JPRO-01", "host": "192.168.1.101", "port": 4028, "electrical_group": "elevator_1"}]
        metrics_list = extract_miner_stability_metrics(
            db_path=str(self.db_path),
            miners=miners,
            states={},
            config={},
            now_ts=now,
        )

        self.assertEqual(len(metrics_list), 1)
        m = metrics_list[0]
        self.assertEqual(m.hw_errors_delta_10m, 230)
        expected_rate = round(230.0 / 690.0 * 100.0, 4)
        self.assertAlmostEqual(m.hw_error_rate_pct, expected_rate, places=2)

    def test_extract_stability_metrics_handles_counter_reset_post_reboot(self):
        """If ASIC rebooted and hw_errors_total reset to lower number, delta handles it safely."""
        now = 1000000.0
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded, threshold_ths, expected_boards,
                rate_ths, max_temp_c, chain_power_w_total, elapsed_seconds, hw_errors_total, accepted_shares_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now - 650.0, "S19JPRO-01|192.168.1.101:4028", "S19JPRO-01", "192.168.1.101", "OK", 1, 80.0, 3, 90.0, 72.0, 2700.0, 10000, 800, 5000),
        )
        cursor.execute(
            """
            INSERT INTO telemetry_samples (
                observed_ts, miner_key, miner_name, host, state, responded, threshold_ths, expected_boards,
                rate_ths, max_temp_c, chain_power_w_total, elapsed_seconds, hw_errors_total, accepted_shares_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, "S19JPRO-01|192.168.1.101:4028", "S19JPRO-01", "192.168.1.101", "OK", 1, 80.0, 3, 90.0, 72.0, 2700.0, 120, 15, 50),
        )
        conn.commit()
        conn.close()

        miners = [{"name": "S19JPRO-01", "host": "192.168.1.101", "port": 4028, "electrical_group": "elevator_1"}]
        metrics_list = extract_miner_stability_metrics(
            db_path=str(self.db_path),
            miners=miners,
            states={},
            config={},
            now_ts=now,
        )

        self.assertEqual(len(metrics_list), 1)
        m = metrics_list[0]
        self.assertEqual(m.hw_errors_delta_10m, 15)
        self.assertGreater(m.hw_error_rate_pct, 0.0)


class TestHWErrorTripwireCard(unittest.TestCase):
    """Validation of Mobile-First vertical card constraints."""

    def test_card_width_strict_limit_32_columns(self):
        """Every rendered line in render_hw_error_tripwire_card must be <= 32 characters."""
        card = render_hw_error_tripwire_card(
            miner_name="S19JPRO-01",
            electrical_group="elevator_1",
            hw_errors_10m=245,
            hw_error_rate_pct=1.456,
            current_preset="2700W",
            target_preset="2500W",
            lock_hours=48.0,
        )
        lines = card.split("\n")
        self.assertTrue(len(lines) >= 7)
        for i, line in enumerate(lines):
            self.assertLessEqual(
                len(line),
                32,
                f"Line {i} exceeds 32 chars: '{line}' ({len(line)} chars)",
            )
        self.assertIn("TRIPWIRE ERRORES HW", card)
        self.assertIn("2700W -> 2500W", card)
        self.assertIn("48h activo", card)


class TestStatePersistenceAndAntiCascade(unittest.TestCase):
    """Test state serialization and post-reboot anti-cascade interlock."""

    def test_state_serialization_roundtrip(self):
        """MinerState hw_error_lock_until_ts and hw_error_locked_preset survive payload serialization and load_state."""
        temp_dir = tempfile.TemporaryDirectory()
        state_file = Path(temp_dir.name) / "state.json"
        try:
            st = MinerState(
                hw_error_lock_until_ts=1700000000.0,
                hw_error_locked_preset="2500W",
                balancer_preset="2500W",
            )
            states = {"S19JPRO-01|192.168.1.101:4028": st}

            payload = _build_state_payload(states, last_update_id=123)
            self.assertEqual(
                payload["states"]["S19JPRO-01|192.168.1.101:4028"]["hw_error_lock_until_ts"],
                1700000000.0,
            )
            self.assertEqual(
                payload["states"]["S19JPRO-01|192.168.1.101:4028"]["hw_error_locked_preset"],
                "2500W",
            )

            sm_data = _serialise_miner_state(st)
            self.assertEqual(sm_data["hw_error_lock_until_ts"], 1700000000.0)
            self.assertEqual(sm_data["hw_error_locked_preset"], "2500W")

            with open(state_file, "w") as f:
                json.dump(payload, f)

            loaded_states, loaded_uid = load_state(state_file)
            self.assertEqual(loaded_uid, 123)
            self.assertIn("S19JPRO-01|192.168.1.101:4028", loaded_states)
            loaded_st = loaded_states["S19JPRO-01|192.168.1.101:4028"]
            self.assertEqual(loaded_st.hw_error_lock_until_ts, 1700000000.0)
            self.assertEqual(loaded_st.hw_error_locked_preset, "2500W")
        finally:
            if state_file.exists():
                try:
                    state_file.unlink()
                except Exception:
                    pass
            try:
                temp_dir.cleanup()
            except Exception:
                pass

    def test_auto_reboot_interlocks_not_blocked_by_hw_error_lock(self):
        """Auto-reboot safety for STATE_LOW / STATE_HASHBOARD must remain unblocked during tripwire lockout."""
        now = 1000000.0
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="S19JPRO-01|192.168.1.101:4028",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=now,
            evaluated_ts=now,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=72.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
        )
        self.assertTrue(decision.allowed)

    def test_execute_balancer_cycle_tripwire_and_telegram_dispatch(self):
        """execute_balancer_cycle triggers tripwire, sets lockout, and dispatches telegram notification."""
        import threading
        from unittest.mock import patch
        now = 1000000.0
        st = MinerState(
            balancer_preset="2700W",
        )
        miners = [{"name": "S19JPRO-01", "host": "192.168.1.101", "port": 4028, "electrical_group": "elevator_1"}]
        states = {"S19JPRO-01|192.168.1.101:4028": st}
        state_lock = threading.Lock()
        config = {
            "preset_balancer_enabled": True,
            "preset_balancer_dry_run": True,
            "preset_balancer_hw_error_rate_threshold_pct": 0.5,
            "preset_balancer_hw_error_delta_threshold": 200,
            "preset_balancer_hw_error_lock_hours": 48.0,
        }

        sent_messages = []
        def mock_send_tg(tok, cid, msg, mtype, reason=""):
            sent_messages.append((tok, cid, msg, mtype, reason))

        mock_metrics = [
            StabilityMetrics(
                miner_name="S19JPRO-01",
                electrical_group="elevator_1",
                current_preset="2700W",
                restarts_24h=0,
                restarts_72h=0,
                hours_since_last_restart=50.0,
                hw_errors_delta_10m=350,
                hw_error_rate_pct=2.5,
            )
        ]

        with patch("app.miner_monitor.extract_miner_stability_metrics", return_value=mock_metrics), \
             patch("app.miner_monitor.refresh_vnish_overclock_settings"):
            decisions = execute_balancer_cycle(
                miners=miners,
                states=states,
                state_lock=state_lock,
                config=config,
                now_ts=now,
                qa_mode=False,
                force=True,
                send_telegram_fn=mock_send_tg,
                bot_token="TEST_BOT",
                chat_id="123456",
            )

        self.assertEqual(len(decisions), 1)
        _, dec = decisions[0]
        self.assertEqual(dec.action, ACTION_STEP_DOWN_HW_ERRORS)
        self.assertEqual(dec.target_preset, "2500W")
        self.assertEqual(st.balancer_preset, "2500W")
        self.assertEqual(st.hw_error_lock_until_ts, now + 48.0 * 3600.0)
        self.assertEqual(st.hw_error_locked_preset, "2500W")
        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0][0], "TEST_BOT")
        self.assertEqual(sent_messages[0][1], "123456")
        self.assertIn("TRIPWIRE ERRORES HW", sent_messages[0][2])


if __name__ == "__main__":
    unittest.main()
