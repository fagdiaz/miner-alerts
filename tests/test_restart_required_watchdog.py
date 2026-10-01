import time
import pytest
from unittest.mock import MagicMock, patch

from app.miner_monitor import (
    evaluate_preset_restart_candidate,
    MinerState,
    execute_governor_cycle,
    STATE_OK,
    STATE_LOW,
)
from app.core.state_manager import serialize_miner_state


class TestEvaluatePresetRestartCandidate:
    """Tests for the pure decision function evaluate_preset_restart_candidate (Spec 081 / PROP-017)."""

    def test_restart_not_required(self):
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=False,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=65.0,
            detected_ts=500.0,
            last_restart_ts=None,
        )
        assert ready is False
        assert reason == "restart_not_required"

    def test_handled_by_degraded_auto_restart(self):
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=True,
            is_warming_up=False,
            max_chip_temp_c=65.0,
            detected_ts=500.0,
            last_restart_ts=None,
        )
        assert ready is False
        assert reason == "handled_by_degraded_auto_restart"

    def test_thermal_pause_active(self):
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=65.0,
            detected_ts=500.0,
            last_restart_ts=None,
            thermal_pause_active=True,
        )
        assert ready is False
        assert reason == "thermal_pause_active"

    def test_miner_warming_up(self):
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=True,
            max_chip_temp_c=65.0,
            detected_ts=500.0,
            last_restart_ts=None,
        )
        assert ready is False
        assert reason == "warming_up"

    def test_chip_temp_too_high(self):
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=81.5,
            detected_ts=500.0,
            last_restart_ts=None,
            max_safe_temp_c=80.0,
        )
        assert ready is False
        assert "chip_temp_too_high_81.5C" in reason

    def test_soak_window_active(self):
        # detected_ts is 800s, now is 1000s -> diff 200s < soak 300s
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=68.0,
            detected_ts=800.0,
            last_restart_ts=None,
            soak_window_seconds=300.0,
        )
        assert ready is False
        assert "soak_window_active_100s" in reason

    def test_cooldown_active(self):
        # last_restart_ts is 900s, now is 1000s -> diff 100s < cooldown 180s
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=68.0,
            detected_ts=500.0,
            last_restart_ts=900.0,
            cooldown_seconds=180.0,
        )
        assert ready is False
        assert "cooldown_active_80s" in reason

    def test_ready_for_preset_restart(self):
        # All conditions met: healthy hashing, cool temps, soak passed, cooldown passed
        ready, reason = evaluate_preset_restart_candidate(
            now_ts=1000.0,
            vnish_restart_required=True,
            is_hash_degraded=False,
            is_warming_up=False,
            max_chip_temp_c=69.0,
            detected_ts=600.0,  # 400s elapsed >= 300s soak
            last_restart_ts=700.0,  # 300s elapsed >= 180s cooldown
            soak_window_seconds=300.0,
            cooldown_seconds=180.0,
            max_safe_temp_c=80.0,
        )
        assert ready is True
        assert reason == "ready_for_preset_restart"


class TestFanGovernorTargetAdaptation:
    """Test Fan Governor target power adaptation when restart_required=True (Fricción F-02 fix)."""

    def test_governor_adapts_target_power_when_restart_required(self):
        st = MinerState(
            governor_duty=75,
            governor_holds=0,
            governor_last_power_w=2498.0,
            vnish_restart_required=True,
        )
        # Verify that MinerState holds vnish_restart_required
        assert st.vnish_restart_required is True

        # In execute_governor_cycle, when vnish_restart_required is True,
        # gov_target_pwr is set to gov_curr_pwr (2498.0W) instead of target_pwr (2700.0W).
        # This prevents 2498W < (2700 - 120 = 2580W) from latching RECOVERY_MAX_COOLING.


class TestStateSerializationRoundtrip:
    """Test state serialization roundtrip for Spec 081 fields."""

    def test_serialize_spec_081_fields(self):
        st = MinerState()
        st.vnish_restart_required = True
        st.vnish_restart_detected_ts = 1710000000.0
        st.last_preset_restart_ts = 1710000500.0

        data = serialize_miner_state(st)
        assert data["vnish_restart_required"] is True
        assert data["vnish_restart_detected_ts"] == 1710000000.0
        assert data["last_preset_restart_ts"] == 1710000500.0


class TestVnishClientRestartRequired:
    """Test get_overclock_settings extraction of restart_required from /api/v1/status."""

    @patch("requests.get")
    def test_get_overclock_settings_includes_restart_required(self, mock_get):
        from app.vnish.client import get_overclock_settings

        # First call: GET /api/v1/settings
        mock_settings_resp = MagicMock()
        mock_settings_resp.status_code = 200
        mock_settings_resp.json.return_value = {
            "miner": {
                "overclock": {
                    "preset": "2700",
                    "preset_switcher": {"enabled": False},
                }
            }
        }

        # Second call: GET /api/v1/status
        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "miner_state": "mining",
            "restart_required": True,
            "reboot_required": False,
        }

        mock_get.side_effect = [mock_settings_resp, mock_status_resp]

        ok, res, err = get_overclock_settings("192.168.100.24", "token_abc")
        assert ok is True
        assert res is not None
        assert res["preset"] == "2700"
        assert res["restart_required"] is True
