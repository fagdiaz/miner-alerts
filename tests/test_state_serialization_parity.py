import json
import unittest
from app.miner_monitor import MinerState, _build_state_payload
from app.core.state_manager import StateManager, serialize_miner_state


class TestStateSerializationParity(unittest.TestCase):
    """Exhaustive tests verifying deterministic state serialization parity (Spec 072)."""

    def test_serialize_miner_state_field_completeness(self):
        st = MinerState(state="OK", low_streak=0, offline_streak=0, ok_streak=5)
        st.governor_duty = 60
        st.balancer_preset = "2500W"
        st.last_rate_ths = 95.5
        st.last_power_w = 2700

        serialized = serialize_miner_state(st)
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["state"], "OK")
        self.assertEqual(serialized["ok_streak"], 5)
        self.assertEqual(serialized["governor_duty"], 60)
        self.assertEqual(serialized["balancer_preset"], "2500W")
        self.assertEqual(serialized["last_rate_ths"], 95.5)
        self.assertEqual(serialized["last_power_w"], 2700)

        # Build state payload round-trip check
        payload = _build_state_payload({"miner_1": st}, last_update_id=100)
        self.assertIn("states", payload)
        self.assertIn("miner_1", payload["states"])
        self.assertEqual(payload["states"]["miner_1"], serialized)

    def test_serialize_miner_state_static_method_parity(self):
        """Verify StateManager.serialize_miner_state produces identical output to serialize_miner_state."""
        st = MinerState(state="WARNING", low_streak=2, offline_streak=0, ok_streak=0)
        st.hw_error_locked_preset = "2100W"
        st.hw_error_lock_until_ts = 1750000000.0
        st.silent_mode_active = True
        st.silent_mode_target_max_duty = 40
        st.inlet_temp_c = 28.5

        res_func = serialize_miner_state(st)
        res_method = StateManager.serialize_miner_state(st)
        self.assertEqual(res_func, res_method)
        self.assertEqual(res_method["hw_error_locked_preset"], "2100W")
        self.assertEqual(res_method["silent_mode_target_max_duty"], 40)
        self.assertEqual(res_method["inlet_temp_c"], 28.5)

    def test_fully_populated_state_json_serializability(self):
        """Verify that all serialized fields can be encoded to JSON without errors."""
        st = MinerState()
        st.state = "DEGRADED"
        st.low_streak = 3
        st.offline_streak = 1
        st.ok_streak = 0
        st.initialized = True
        st.last_elapsed = 45
        st.last_seen_ts = 1700000000.0
        st.reboot_pending_until = 1700000100.0
        st.reboot_pending_reason = "low_hashrate"
        st.reboot_pending_elapsed = 100
        st.last_reboot_ts = 1699990000.0
        st.low_since_ts = 1699995000.0
        st.hashboard_since_ts = 1699996000.0
        st.last_manual_reboot_ts = 1699980000.0
        st.last_auto_reboot_ts = 1699985000.0
        st.last_auto_restart_ts = 1699986000.0
        st.auto_restart_count = 2
        st.auto_reboot_timestamps = [1699985000.0]
        st.degraded_mode = True
        st.last_hourly_status_ts = 1700000000.0
        st.snooze_until_ts = 1700003600.0
        st.cooling_streak = 1
        st.last_cooling_warning_ts = 1699999000.0
        st.efficiency_streak = 2
        st.last_efficiency_warning_ts = 1699998000.0
        st.baseline_frequency_mhz = 650.0
        st.last_preset_warning_ts = 1699997000.0
        st.governor_duty = 85
        st.governor_holds = 3
        st.governor_last_change_ts = 1699999500.0
        st.governor_failures = 0
        st.governor_last_action = "STEP_UP"
        st.governor_last_temp_c = 72.5
        st.governor_last_power_w = 2750.0
        st.balancer_preset = "2800W"
        st.balancer_last_change_ts = 1699999000.0
        st.balancer_last_action = "HOLD_STABLE"
        st.balancer_last_reason = "margin_ok"
        st.hw_error_lock_until_ts = 1700086400.0
        st.hw_error_locked_preset = "2500W"
        st.vnish_discovered_target_power_w = 2800.0
        st.vnish_discovered_preset = "2800W"
        st.vnish_discovered_top_preset = "2800W"
        st.vnish_discovered_switcher_enabled = False
        st.vnish_discovered_ts = 1700000000.0
        st.silent_mode_active = True
        st.silent_mode_revert_ts = 1700007200.0
        st.silent_mode_prev_duty = 60
        st.silent_mode_prev_preset = "2700W"
        st.silent_mode_target_max_duty = 50
        st.is_shutdown_maintenance = False
        st.shutdown_maintenance_ts = 0.0
        st.last_rate_ths = 104.2
        st.last_active_boards = 3
        st.last_expected_boards = 3
        st.last_max_chip_temp = 73.0
        st.last_fan_duty_percent = 85.0
        st.last_power_w = 2820.0
        st.last_efficiency_j_th = 27.1
        st.last_responded = True
        st.inlet_temp_c = 24.5
        st.chain_warnings_ts = {"2": 1700001000.0}

        serialized = StateManager.serialize_miner_state(st)
        encoded_json = json.dumps(serialized)
        decoded = json.loads(encoded_json)

        # Confirm all populated attributes match in round-trip
        self.assertEqual(decoded["state"], "DEGRADED")
        self.assertEqual(decoded["last_rate_ths"], 104.2)
        self.assertEqual(decoded["governor_duty"], 85)
        self.assertEqual(decoded["balancer_preset"], "2800W")
        self.assertEqual(decoded["inlet_temp_c"], 24.5)
        self.assertEqual(decoded["auto_reboot_timestamps"], [1699985000.0])
        self.assertEqual(decoded["chain_warnings_ts"], {"2": 1700001000.0})


if __name__ == "__main__":
    unittest.main()

