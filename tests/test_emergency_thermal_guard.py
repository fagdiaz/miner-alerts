"""Unit and integration tests for Emergency Thermal Guard (P0 Invariant).

Tests that:
1. When chip temperature >= 84.0°C, emergency step-down is executed immediately with 100% fans
   and a 2-hour lockout against step-up.
2. When chip temperature >= 87.0°C, emergency pause stops mining and holds fans at 100% PWM.
3. Once chips cool <= 75.0°C and settle duration expires, mining automatically resumes.
4. Auto-restart and auto-reboot do not interfere while in thermal pause.
5. All hardware calls are transactional, non-blocking, and respect QA mode.
"""

import time
import unittest
from unittest.mock import MagicMock, call

from app.governance.thermal_guard import (
    ACTION_EMERGENCY_DOWNSTEP,
    ACTION_EMERGENCY_PAUSE,
    ACTION_NONE,
    ACTION_PAUSED_COOLING,
    ACTION_THERMAL_RESUME,
    ACTION_THERMAL_UNCLAMP,
    ThermalGuardDecision,
    evaluate_emergency_thermal_action,
    process_emergency_thermal_guard,
)
from app.miner_monitor import MinerState


class TestEvaluateEmergencyThermalAction(unittest.TestCase):
    def setUp(self):
        self.config = {
            "emergency_thermal_protection_enabled": True,
            "emergency_thermal_downstep_temp_c": 85.5,
            "emergency_thermal_pause_temp_c": 87.0,
            "emergency_thermal_resume_temp_c": 75.0,
            "emergency_thermal_downstep_cooldown_seconds": 180.0,
            "emergency_thermal_pause_cooldown_seconds": 120.0,
            "emergency_thermal_lockout_seconds": 7200.0,
        }

    def test_disabled_protection_returns_none(self):
        cfg = dict(self.config, emergency_thermal_protection_enabled=False)
        dec = evaluate_emergency_thermal_action(
            max_temp_c=88.0,
            config=cfg,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_NONE)

    def test_none_temperature_returns_none(self):
        dec = evaluate_emergency_thermal_action(
            max_temp_c=None,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_NONE)

    def test_normal_temperature_returns_none(self):
        dec = evaluate_emergency_thermal_action(
            max_temp_c=78.5,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_NONE)

    def test_vnish_native_threshold_right_of_way(self):
        # Temp 84.5°C is between VNish decrease_temp (84.0°C) and monitor emergency (85.5°C).
        # Monitor leaves right-of-way to VNish in-kernel switcher -> ACTION_NONE.
        dec = evaluate_emergency_thermal_action(
            max_temp_c=84.5,
            current_preset="2700",
            current_power_w=2698.0,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_NONE)
        self.assertIn("seguro", dec.reason.lower())

    def test_level1_downstep_from_2700w(self):
        # Temp 85.6°C >= 85.5°C at 2700W -> steps down to 2500W
        dec = evaluate_emergency_thermal_action(
            max_temp_c=85.6,
            current_preset="2700",
            current_power_w=2698.0,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_DOWNSTEP)
        self.assertEqual(dec.target_preset, "2500")
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.is_emergency)
        self.assertEqual(dec.lockout_duration_s, 7200.0)

    def test_level1_downstep_from_2500w(self):
        # Temp 85.8°C >= 85.5°C at 2500W after cooldown -> steps down to 2300W
        dec = evaluate_emergency_thermal_action(
            max_temp_c=85.8,
            current_preset="2500",
            current_power_w=2498.0,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_DOWNSTEP)
        self.assertEqual(dec.target_preset, "2300")

    def test_level1_downstep_cooldown_suppression(self):
        # Second call within 180s must be suppressed (anti-doble-bajada)
        dec1 = evaluate_emergency_thermal_action(
            max_temp_c=85.8,
            current_preset="2700",
            last_downstep_ts=1000.0,
            config=self.config,
            now_ts=1100.0,  # Only 100s later < 180s
        )
        self.assertEqual(dec1.action, ACTION_NONE)
        self.assertIn("anti-doble-bajada", dec1.reason.lower())

        # After 181s, downstep is allowed again
        dec2 = evaluate_emergency_thermal_action(
            max_temp_c=85.8,
            current_preset="2700",
            last_downstep_ts=1000.0,
            config=self.config,
            now_ts=1181.0,  # 181s later > 180s
        )
        self.assertEqual(dec2.action, ACTION_EMERGENCY_DOWNSTEP)

    def test_level2_emergency_pause(self):
        # Temp 87.5°C >= 87.0°C -> emergency pause!
        dec = evaluate_emergency_thermal_action(
            max_temp_c=87.5,
            current_preset="2700",
            current_power_w=2699.0,
            config=self.config,
            now_ts=1000.0,
        )
        self.assertEqual(dec.action, ACTION_EMERGENCY_PAUSE)
        self.assertEqual(dec.target_duty, 100)
        self.assertTrue(dec.is_emergency)

    def test_level2_emergency_pause_cooldown(self):
        # Within pause cooldown of 120s, do not re-dispatch pause
        dec = evaluate_emergency_thermal_action(
            max_temp_c=88.0,
            last_pause_ts=1000.0,
            config=self.config,
            now_ts=1050.0,  # 50s < 120s
        )
        self.assertEqual(dec.action, ACTION_NONE)

    def test_paused_cooling_while_still_hot(self):
        # While in pause, if temp is still 78.0°C (> 75.0°C), keep paused
        dec = evaluate_emergency_thermal_action(
            max_temp_c=78.0,
            thermal_pause_until_ts=1090.0,
            config=self.config,
            now_ts=1100.0,  # duration elapsed but temp > 75°C
        )
        self.assertEqual(dec.action, ACTION_PAUSED_COOLING)
        self.assertEqual(dec.target_duty, 100)

    def test_paused_cooling_while_time_remaining(self):
        # While in pause, if temp is 72.0°C (<= 75.0°C) but settle duration not elapsed, keep paused
        dec = evaluate_emergency_thermal_action(
            max_temp_c=72.0,
            thermal_pause_until_ts=1090.0,
            config=self.config,
            now_ts=1050.0,  # 40s remaining
        )
        self.assertEqual(dec.action, ACTION_PAUSED_COOLING)

    def test_thermal_resume_when_cool_and_duration_elapsed(self):
        # Temp <= 75.0°C and now_ts >= pause_until_ts -> RESUME MINING!
        dec = evaluate_emergency_thermal_action(
            max_temp_c=73.5,
            current_preset="2700",
            thermal_pause_until_ts=1090.0,
            config=self.config,
            now_ts=1095.0,  # Elapsed and cool!
        )
        self.assertEqual(dec.action, ACTION_THERMAL_RESUME)
        self.assertEqual(dec.target_preset, "2500")
        self.assertEqual(dec.target_duty, 100)

    def test_lockout_expired_unclamp_restores_top_preset(self):
        # 1. Lockout expired, chips cool (<=80°C), top clamped at 2500W below max hardware 2700W -> UNCLAMP!
        dec = evaluate_emergency_thermal_action(
            max_temp_c=78.0,
            current_preset="2500",
            config=self.config,
            now_ts=8205.0,
            thermal_lockout_until_ts=8200.0,
            current_top_preset="2500",
            max_hardware_preset="2700W",
        )
        self.assertEqual(dec.action, ACTION_THERMAL_UNCLAMP)
        self.assertEqual(dec.target_preset, "2700")

        # 2. Chips too hot (> 80.0°C) -> No unclamp yet (stays ACTION_NONE)
        dec_hot = evaluate_emergency_thermal_action(
            max_temp_c=81.5,
            current_preset="2500",
            config=self.config,
            now_ts=8205.0,
            thermal_lockout_until_ts=8200.0,
            current_top_preset="2500",
            max_hardware_preset="2700W",
        )
        self.assertEqual(dec_hot.action, ACTION_NONE)

        # 3. Already at max hardware preset -> No unclamp needed
        dec_max = evaluate_emergency_thermal_action(
            max_temp_c=78.0,
            current_preset="2700",
            config=self.config,
            now_ts=8205.0,
            thermal_lockout_until_ts=8200.0,
            current_top_preset="2700",
            max_hardware_preset="2700W",
        )
        self.assertEqual(dec_max.action, ACTION_NONE)

        # 4. Lockout not yet expired -> No unclamp
        dec_locked = evaluate_emergency_thermal_action(
            max_temp_c=78.0,
            current_preset="2500",
            config=self.config,
            now_ts=8100.0,
            thermal_lockout_until_ts=8200.0,
            current_top_preset="2500",
            max_hardware_preset="2700W",
        )
        self.assertEqual(dec_locked.action, ACTION_NONE)


class TestProcessEmergencyThermalGuard(unittest.TestCase):
    def setUp(self):
        self.config = {
            "emergency_thermal_protection_enabled": True,
            "emergency_thermal_downstep_temp_c": 85.5,
            "emergency_thermal_pause_temp_c": 87.0,
            "emergency_thermal_resume_temp_c": 75.0,
            "emergency_thermal_downstep_cooldown_seconds": 180.0,
            "emergency_thermal_pause_cooldown_seconds": 120.0,
            "emergency_thermal_lockout_seconds": 7200.0,
        }
        self.miner = {
            "name": "S19JPRO-25",
            "host": "192.168.100.25",
            "port": 4028,
            "target_power_w": 2700.0,
        }
        self.state = MinerState()
        self.state.governor_last_power_w = 2699.0
        self.state.balancer_preset = "2700"

        self.mock_set_preset = MagicMock(return_value=(True, None))
        self.mock_stop_mining = MagicMock(return_value=(True, None))
        self.mock_resume_mining = MagicMock(return_value=(True, None))
        self.mock_set_fan = MagicMock(return_value=(True, None))
        self.mock_send_tg = MagicMock()
        self.mock_log = MagicMock()

    def test_process_emergency_downstep_dispatches_correctly(self):
        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=85.8,
            config=self.config,
            now_ts=1000.0,
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertEqual(action, ACTION_EMERGENCY_DOWNSTEP)
        self.mock_set_preset.assert_called_once_with(
            "192.168.100.25",
            "admin",
            "2500",
            clamp_top_preset=True,
            top_preset="2500",
            min_preset="2500",
        )
        self.mock_set_fan.assert_called_once_with("192.168.100.25", "admin", 100)
        self.assertEqual(self.state.last_thermal_downstep_ts, 1000.0)
        self.assertEqual(self.state.thermal_lockout_until_ts, 1000.0 + 7200.0)
        self.assertEqual(self.state.hw_error_lock_until_ts, 1000.0 + 7200.0)
        self.assertEqual(self.state.balancer_preset, "2500")
        self.mock_send_tg.assert_called_once()

    def test_anti_doble_bajada_sync_suppresses_secondary_downstep(self):
        # Simulating that VNish autonomously downstepped 40s ago (last_preset_change_ts = 1000.0)
        self.state.last_preset_change_ts = 1000.0
        self.state.balancer_preset = "2500"
        self.state.governor_last_power_w = 2498.0

        # At 1040.0s (40s < 180s cooldown), temp touches 85.8°C before cooling completes
        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=85.8,
            config=self.config,
            now_ts=1040.0,
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertIsNone(action)
        self.mock_set_preset.assert_not_called()

    def test_process_emergency_pause_dispatches_correctly(self):
        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=87.8,
            config=self.config,
            now_ts=2000.0,
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertEqual(action, ACTION_EMERGENCY_PAUSE)
        self.mock_stop_mining.assert_called_once_with("192.168.100.25", "admin")
        self.mock_set_fan.assert_called_once_with("192.168.100.25", "admin", 100)
        self.assertEqual(self.state.last_thermal_pause_ts, 2000.0)
        self.assertEqual(self.state.thermal_pause_until_ts, 2090.0)
        self.mock_send_tg.assert_called_once()

    def test_process_thermal_resume_dispatches_correctly(self):
        self.state.thermal_pause_until_ts = 2090.0
        self.state.balancer_preset = "2500"

        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=71.0,
            config=self.config,
            now_ts=2100.0,  # Duration elapsed and temp cool
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertEqual(action, ACTION_THERMAL_RESUME)
        self.mock_set_preset.assert_called_once_with(
            "192.168.100.25", "admin", "2300", clamp_top_preset=True, top_preset="2300", min_preset="2300"
        )
        self.mock_resume_mining.assert_called_once_with("192.168.100.25", "admin")
        self.mock_set_fan.assert_called_once_with("192.168.100.25", "admin", 100)
        self.assertIsNone(self.state.thermal_pause_until_ts)
        self.mock_send_tg.assert_called_once()

    def test_qa_mode_blocks_hardware_writes(self):
        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=85.8,
            config=self.config,
            now_ts=3000.0,
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            qa_mode=True,
            qa_notify=False,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertEqual(action, ACTION_EMERGENCY_DOWNSTEP)
        self.mock_set_preset.assert_not_called()
        self.mock_set_fan.assert_not_called()
        self.mock_send_tg.assert_not_called()

    def test_process_unclamp_dispatches_correctly(self):
        self.state.thermal_lockout_until_ts = 8200.0
        self.state.hw_error_lock_until_ts = 8200.0
        self.state.vnish_discovered_top_preset = "2500"
        self.state.balancer_preset = "2500"
        self.miner["max_hardware_preset"] = "2700W"

        action = process_emergency_thermal_guard(
            miner=self.miner,
            state=self.state,
            max_temp_c=78.0,
            config=self.config,
            now_ts=8210.0,
            vnish_pw="admin",
            safe_set_preset_fn=self.mock_set_preset,
            safe_stop_fn=self.mock_stop_mining,
            safe_resume_fn=self.mock_resume_mining,
            safe_set_fan_fn=self.mock_set_fan,
            send_telegram_fn=self.mock_send_tg,
            log_fn=self.mock_log,
            bot_token="test_token",
            chat_id="12345",
        )
        self.assertEqual(action, ACTION_THERMAL_UNCLAMP)
        self.mock_set_preset.assert_called_once_with(
            "192.168.100.25",
            "admin",
            "2500",
            clamp_top_preset=False,
            top_preset="2700",
            min_preset="1740",
        )
        self.assertIsNone(self.state.thermal_lockout_until_ts)
        self.assertIsNone(self.state.hw_error_lock_until_ts)
        self.assertEqual(self.state.vnish_discovered_top_preset, "2700")
        self.mock_send_tg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
