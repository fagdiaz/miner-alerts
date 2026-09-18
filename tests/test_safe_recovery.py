import unittest
from app.governance.safe_recovery import (
    SafeRecoveryState,
    RecoveryDecision,
    evaluate_safe_recovery,
    evaluate_headroom_chilling,
    ACTION_WAIT_SETTLE,
    ACTION_PRE_CLAMP_AND_RESTART,
    ACTION_HOLD_DEGRADED,
    ACTION_STAGED_RAMP_UP,
    ACTION_NORMAL,
)


class TestSafeRecovery(unittest.TestCase):
    def test_passive_settle_window_holds_for_120s(self):
        t0 = 1000.0
        state = SafeRecoveryState(miner_name="25")
        
        # First tick detecting stopped state
        dec, st1 = evaluate_safe_recovery(state, current_ts=t0, miner_state="stopped", current_rate_ths=0.0)
        self.assertEqual(dec.action, ACTION_WAIT_SETTLE)
        self.assertEqual(st1.stopped_since_ts, t0)
        
        # Second tick at 60s (inside 120s window) -> still WAIT_SETTLE
        dec2, st2 = evaluate_safe_recovery(st1, current_ts=t0 + 60.0, miner_state="stopped", current_rate_ths=0.0)
        self.assertEqual(dec2.action, ACTION_WAIT_SETTLE)
        self.assertFalse(dec2.trigger_restart)

    def test_settle_window_expiration_triggers_pre_clamp_and_restart(self):
        t0 = 1000.0
        state = SafeRecoveryState(miner_name="25", stopped_since_ts=t0, pre_clamp_preset="1800", original_preset="2300")
        
        # At 125s (window expired) -> PRE_CLAMP_AND_RESTART at 1800W
        dec, st = evaluate_safe_recovery(state, current_ts=t0 + 125.0, miner_state="stopped", current_rate_ths=0.0)
        self.assertEqual(dec.action, ACTION_PRE_CLAMP_AND_RESTART)
        self.assertEqual(dec.target_preset, "1800")
        self.assertTrue(dec.clamp_top_preset)
        self.assertTrue(dec.trigger_restart)
        self.assertEqual(st.recovery_attempts, 1)
        self.assertTrue(st.is_pre_clamped)

    def test_physical_chain_fault_inhibits_secondary_restarts(self):
        t0 = 1000.0
        # State already attempted 1 recovery and chain fault is physically present
        state = SafeRecoveryState(
            miner_name="25",
            stopped_since_ts=t0,
            recovery_attempts=1,
            max_recovery_attempts=1,
            pre_clamp_preset="1800",
            is_pre_clamped=True,
        )
        
        dec, st = evaluate_safe_recovery(
            state,
            current_ts=t0 + 200.0,
            miner_state="stopped",
            chain_fault_present=True,
            current_rate_ths=0.0,
        )
        self.assertEqual(dec.action, ACTION_HOLD_DEGRADED)
        self.assertFalse(dec.trigger_restart)
        self.assertIn("Inhibición defensiva", dec.reason)

    def test_staged_ramp_up_soak_and_restoration(self):
        t0 = 1000.0
        state = SafeRecoveryState(
            miner_name="25",
            is_pre_clamped=True,
            original_preset="2500",
            pre_clamp_preset="1800",
            staged_ramp_up_pending=True,
        )
        
        # Miner reaches OK (rate >= 60.0) -> starts soak
        dec1, st1 = evaluate_safe_recovery(
            state,
            current_ts=t0,
            miner_state="OK",
            current_rate_ths=85.0,
            threshold_ths=60.0,
            ramp_up_soak_seconds=180.0,
        )
        self.assertEqual(dec1.action, ACTION_STAGED_RAMP_UP)
        self.assertEqual(st1.staged_ramp_up_soak_start_ts, t0)
        self.assertEqual(dec1.target_preset, "1800")
        
        # During soak (at 90s) -> holds pre-clamp
        dec2, st2 = evaluate_safe_recovery(
            st1,
            current_ts=t0 + 90.0,
            miner_state="OK",
            current_rate_ths=85.0,
            threshold_ths=60.0,
            ramp_up_soak_seconds=180.0,
        )
        self.assertEqual(dec2.action, ACTION_STAGED_RAMP_UP)
        self.assertEqual(dec2.target_preset, "1800")
        
        # After 185s (soak completed) -> restores original 2500W
        dec3, st3 = evaluate_safe_recovery(
            st2,
            current_ts=t0 + 185.0,
            miner_state="OK",
            current_rate_ths=85.0,
            threshold_ths=60.0,
            ramp_up_soak_seconds=180.0,
        )
        self.assertEqual(dec3.action, ACTION_STAGED_RAMP_UP)
        self.assertEqual(dec3.target_preset, "2500")
        self.assertFalse(st3.is_pre_clamped)
        self.assertFalse(st3.staged_ramp_up_pending)

    def test_headroom_chilling_conditions(self):
        # Case 1: Miner at 2500W, max 2700W, temp 81.5°C, fans 90% -> SHOULD CHILL
        should_chill, reason = evaluate_headroom_chilling(
            target_power_w=2500.0,
            max_power_w=2700.0,
            current_temp_c=81.5,
            current_fan_duty=90,
            step_up_min_margin_c=3.0,
            saturate_temp_c=84.0,
        )
        self.assertTrue(should_chill)
        self.assertIn("Headroom Chilling", reason)

        # Case 2: Fans already at 99% -> NO CHILL
        should_chill, reason = evaluate_headroom_chilling(
            target_power_w=2500.0,
            max_power_w=2700.0,
            current_temp_c=81.5,
            current_fan_duty=99,
        )
        self.assertFalse(should_chill)
        self.assertIn("Ventiladores ya están al máximo", reason)

        # Case 3: Already at max power 2700W -> NO CHILL
        should_chill, reason = evaluate_headroom_chilling(
            target_power_w=2700.0,
            max_power_w=2700.0,
            current_temp_c=81.0,
            current_fan_duty=85,
        )
        self.assertFalse(should_chill)
        self.assertIn("potencia máxima", reason)

        # Case 4: Temperature already very low (75°C) -> NO CHILL (margin is sufficient)
        should_chill, reason = evaluate_headroom_chilling(
            target_power_w=2500.0,
            max_power_w=2700.0,
            current_temp_c=75.0,
            current_fan_duty=80,
        )
        self.assertFalse(should_chill)
        self.assertIn("Margen térmico suficiente", reason)

    def test_stock_firmware_fallback_inhibition(self):
        """Spec 075 / Miner 24 Incident: Fallback to factory Bitmain NAND inhibits restart."""
        state = SafeRecoveryState(miner_name="24")
        dec, st = evaluate_safe_recovery(
            state,
            current_ts=1000.0,
            miner_state="stopped",
            current_rate_ths=0.0,
            stock_firmware_fallback=True,
        )
        self.assertEqual(dec.action, "INHIBIT_HARDWARE_FAULT")
        self.assertFalse(dec.trigger_restart)
        self.assertIn("firmware de fábrica Bitmain", dec.reason)

    def test_sensor_fault_inhibition(self):
        """Spec 075 / Miner 24 Incident: Physical I2C thermal sensor fault inhibits restart."""
        state = SafeRecoveryState(miner_name="24")
        dec, st = evaluate_safe_recovery(
            state,
            current_ts=1000.0,
            miner_state="stopped",
            current_rate_ths=0.0,
            sensor_fault_present=True,
        )
        self.assertEqual(dec.action, "INHIBIT_HARDWARE_FAULT")
        self.assertFalse(dec.trigger_restart)
        self.assertIn("sensor térmico I2C", dec.reason)


if __name__ == "__main__":
    unittest.main()
