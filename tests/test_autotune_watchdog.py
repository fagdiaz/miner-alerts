"""Unit tests for Autotune Stall Watchdog (Spec 078 / PROP-013)."""

from datetime import datetime
import unittest

from app.governance.autotune_watchdog import (
    ACTION_AUTOTUNE_ACTIVE_MINING,
    ACTION_AUTOTUNE_OK,
    ACTION_AUTOTUNE_STALLED,
    AutotuneStallDecision,
    AutotuneWatchdogState,
    determine_safe_rescue_preset,
    evaluate_autotune_stall,
)


class TestAutotuneStallEvaluation(unittest.TestCase):
    """Tests the pure deterministic evaluation of autotune stalls."""

    def test_normal_mining_state_is_not_stalled(self):
        dec = evaluate_autotune_stall(
            miner_name="S19JPRO-23",
            miner_state="mining",
            miner_state_time=1200,
            current_hashrate_ths=101.5,
            current_preset="2700W",
        )
        self.assertFalse(dec.is_stalled)
        self.assertEqual(dec.action, ACTION_AUTOTUNE_OK)
        self.assertFalse(dec.requires_step_down)

    def test_tuning_within_timeout_is_not_stalled(self):
        # 300s into tuning (< 600s timeout)
        dec = evaluate_autotune_stall(
            miner_name="S19JPRO-25",
            miner_state="auto-tuning",
            miner_state_time=300,
            current_hashrate_ths=0.0,
            current_preset="2700W",
            timeout_s=600.0,
        )
        self.assertFalse(dec.is_stalled)
        self.assertEqual(dec.action, ACTION_AUTOTUNE_OK)
        self.assertFalse(dec.requires_step_down)
        self.assertIn("restan 300s", dec.reason)

    def test_tuning_with_healthy_hashrate_is_active_mining(self):
        # 1200s into tuning, but hashrate is 98.5 TH/s (like Miner 24 today)
        dec = evaluate_autotune_stall(
            miner_name="S19JPRO-24",
            miner_state="auto-tuning",
            miner_state_time=1200,
            current_hashrate_ths=98.5,
            current_preset="2700W",
            timeout_s=600.0,
            min_hashrate_ths=20.0,
        )
        self.assertFalse(dec.is_stalled)
        self.assertEqual(dec.action, ACTION_AUTOTUNE_ACTIVE_MINING)
        self.assertFalse(dec.requires_step_down)
        self.assertIn("hasheando con normalidad", dec.reason)

    def test_tuning_exceeding_timeout_with_low_hashrate_triggers_stall(self):
        # 2708s in auto-tuning with 0.0 TH/s (The Miner 25 incident today!)
        dec = evaluate_autotune_stall(
            miner_name="S19JPRO-25",
            miner_state="auto-tuning",
            miner_state_time=2708,
            current_hashrate_ths=0.0,
            current_preset="2700W",
            timeout_s=600.0,
            min_hashrate_ths=20.0,
        )
        self.assertTrue(dec.is_stalled)
        self.assertEqual(dec.action, ACTION_AUTOTUNE_STALLED)
        self.assertTrue(dec.requires_step_down)
        self.assertEqual(dec.safe_preset, "2500W")
        self.assertIn("AUTOTUNE_STALLED", dec.reason)
        self.assertIn("2708s (> 600s)", dec.reason)

    def test_determine_safe_rescue_preset(self):
        self.assertEqual(determine_safe_rescue_preset("2700W"), "2500W")
        self.assertEqual(determine_safe_rescue_preset("2970W"), "2500W")
        self.assertEqual(determine_safe_rescue_preset("2500W"), "2300W")
        self.assertEqual(determine_safe_rescue_preset("2300W"), "2150W")
        self.assertEqual(determine_safe_rescue_preset("2150W"), "2000W")

    def test_determine_safe_rescue_preset_with_hardware_ceiling(self):
        # Miner 25 has max_hardware_preset="2500W", trapped at 2700W
        safe = determine_safe_rescue_preset("2700W", max_hardware_preset="2500W")
        self.assertEqual(safe, "2500W")


class TestAutotuneWatchdogState(unittest.TestCase):
    """Tests the state tracking and locking of stalled miners."""

    def test_record_rescue_and_lock(self):
        st = AutotuneWatchdogState()
        self.assertFalse(st.is_hardware_locked("S19JPRO-25")[0])

        st.record_stall_rescue("S19JPRO-25", locked_preset="2500W", now_ts=1000.0)
        is_locked, ceiling = st.is_hardware_locked("S19JPRO-25")
        self.assertTrue(is_locked)
        self.assertEqual(ceiling, "2500W")

        # Also works with short name "25"
        is_locked_short, ceiling_short = st.is_hardware_locked("25")
        self.assertTrue(is_locked_short)
        self.assertEqual(ceiling_short, "2500W")

    def test_clear_lock(self):
        st = AutotuneWatchdogState()
        st.record_stall_rescue("S19JPRO-25", locked_preset="2500W", now_ts=1000.0)
        st.clear_lock("S19JPRO-25")
        self.assertFalse(st.is_hardware_locked("S19JPRO-25")[0])

    def test_serialization_roundtrip(self):
        st = AutotuneWatchdogState()
        st.record_stall_rescue("S19JPRO-25", locked_preset="2500W", now_ts=1500.0)
        st.record_stall_rescue("S19JPRO-26", locked_preset="2300W", now_ts=1600.0)

        data = st.to_dict()
        loaded = AutotuneWatchdogState.from_dict(data)

        self.assertEqual(st.stalled_miners, loaded.stalled_miners)
        self.assertEqual(st.hardware_ceiling_locks, loaded.hardware_ceiling_locks)
        self.assertEqual(st.last_rescue_ts, loaded.last_rescue_ts)

    def test_check_autotune_watchdog_with_preprovided_summaries(self):
        from app.miner_monitor import check_autotune_watchdog
        import threading
        miners = [{"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028}]
        states = {}
        state_lock = threading.Lock()
        config = {"autotune_timeout_s": 600.0}
        summaries = {
            "192.168.100.23": {
                "miner_state": "mining",
                "miner_state_time": 5000,
                "hr_realtime_ths": 95.0,
                "power_usage_w": 2500,
            }
        }
        res = check_autotune_watchdog(
            miners=miners,
            states=states,
            state_lock=state_lock,
            config=config,
            now_ts=1000.0,
            qa_mode=True,
            summaries=summaries,
        )
        self.assertEqual(res, [])

    def test_check_autotune_watchdog_suppressed_by_intervention_governance(self):
        from app.miner_monitor import check_autotune_watchdog
        import app.miner_monitor as mm
        from app.governance.intervention_policy import InterventionGovernance
        import threading

        miners = [{"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028}]
        states = {}
        state_lock = threading.Lock()
        config = {"autotune_timeout_s": 600.0}
        summaries = {
            "192.168.100.26": {
                "miner_state": "auto-tuning",
                "miner_state_time": 4000,
                "hr_realtime_ths": 10.0,
                "power_usage_w": 2500,
            }
        }

        old_gov = getattr(mm, "_GLOBAL_INTERVENTION_GOV", None)
        try:
            mm._GLOBAL_INTERVENTION_GOV = InterventionGovernance(master_enabled=False, disabled_reason="vnish_libre")
            res = check_autotune_watchdog(
                miners=miners,
                states=states,
                state_lock=state_lock,
                config=config,
                now_ts=1000.0,
                qa_mode=False,
                summaries=summaries,
            )
            self.assertEqual(res, [])
        finally:
            mm._GLOBAL_INTERVENTION_GOV = old_gov


if __name__ == "__main__":
    unittest.main()
