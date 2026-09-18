"""Unit tests for Paired Elevator Contingency, Inrush Dampener, and Warmup Floor (Spec 074 / PROP-009)."""

import unittest
from unittest.mock import MagicMock, patch

from app.governance.adaptive_contingency import (
    ACTION_HOLD_CONTINGENCY,
    ACTION_NO_ACTION,
    ACTION_RESTORE_INRUSH_DAMPENER,
    ACTION_RESTORE_NOMINAL,
    ACTION_STEP_DOWN_CANARY,
    ACTION_STEP_DOWN_LIMIT,
    ACTION_STEP_DOWN_PARTNER,
    ACTION_STEP_UP_SOAK,
    DEFAULT_CANARY_MAP,
    DEFAULT_INRUSH_DAMPENER_SECONDS,
    DEFAULT_SOAK_SECONDS,
    GroupContingencyState,
    evaluate_canary_contingency,
    find_next_preset_tier,
    find_previous_preset_tier,
    is_canary_miner,
    normalize_miner_name,
)
from app.governance.fan_governor import (
    ACTION_EMERGENCY_SPIKE,
    ACTION_HOLD_DWELL,
    ACTION_HOLD_TARGET,
    ACTION_RECOVERY_MAX_COOLING,
    ACTION_STEP_DOWN,
    ACTION_STEP_UP,
    GovernorConfig,
    compute_governor_step,
)
from app.vnish.client import (
    DEFAULT_HTTP_TIMEOUT,
    safe_set_miner_preset,
    set_miner_preset,
)


class TestPairedElevatorContingencyH1(unittest.TestCase):
    """H1 Tests: Software name normalization and canary mapping resilience."""

    def test_canonical_and_display_name_matching(self):
        """Ensure variant names match their canonical form."""
        self.assertEqual(normalize_miner_name("24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("Miner 24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("s19jpro-24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("S19JPRO-24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("23"), "S19JPRO-23")
        self.assertEqual(normalize_miner_name("25"), "S19JPRO-25")
        self.assertEqual(normalize_miner_name("26"), "S19JPRO-26")

    def test_is_canary_with_varied_names(self):
        """Canary detection succeeds regardless of whether raw ID or display name is used."""
        self.assertTrue(is_canary_miner("24", "elevator_1"))
        self.assertTrue(is_canary_miner("S19JPRO-24", "elevator_1"))
        self.assertTrue(is_canary_miner("Miner 24", "elevator_1"))
        self.assertFalse(is_canary_miner("23", "elevator_1"))
        self.assertFalse(is_canary_miner("S19JPRO-23", "elevator_1"))

        self.assertTrue(is_canary_miner("25", "elevator_2"))
        self.assertTrue(is_canary_miner("S19JPRO-25", "elevator_2"))
        self.assertFalse(is_canary_miner("26", "elevator_2"))
        self.assertFalse(is_canary_miner("S19JPRO-26", "elevator_2"))

    def test_miner_list_lookup_matching(self):
        """Simulate miner monitor target lookup when config has display names and decision has canonical."""
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028},
        ]
        decision_target = "24"

        # Raw matching fails
        raw_match = next((m for m in miners if m.get("name") == decision_target), None)
        self.assertIsNone(raw_match, "Raw string matching should fail on disparate naming formats")

        # Normalized matching succeeds
        norm_match = next(
            (m for m in miners if normalize_miner_name(m.get("name", "")) == normalize_miner_name(decision_target)),
            None,
        )
        self.assertIsNotNone(norm_match)
        self.assertEqual(norm_match["host"], "192.168.100.24")


class TestPairedElevatorContingencyH2(unittest.TestCase):
    """H2 Tests: Vnish preset clamping (clamp_top_preset) to prevent daemon fighting."""

    @patch("requests.post")
    def test_preset_payload_contains_clamped_top_preset(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, err = set_miner_preset("192.168.100.24", "tok_xyz", "2500W", clamp_top_preset=True)
        self.assertTrue(ok)
        self.assertIsNone(err)

        mock_post.assert_called_once_with(
            "http://192.168.100.24/api/v1/settings",
            headers={
                "Authorization": "Bearer tok_xyz",
                "Content-Type": "application/json",
            },
            json={
                "miner": {
                    "overclock": {
                        "preset": "2500",
                        "preset_switcher": {
                            "top_preset": "2500"
                        },
                    }
                }
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )

    @patch("requests.post")
    def test_preset_payload_without_clamping(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, err = set_miner_preset("192.168.100.24", "tok_xyz", "2500W", clamp_top_preset=False)
        self.assertTrue(ok)
        self.assertIsNone(err)

        mock_post.assert_called_once_with(
            "http://192.168.100.24/api/v1/settings",
            headers={
                "Authorization": "Bearer tok_xyz",
                "Content-Type": "application/json",
            },
            json={
                "miner": {
                    "overclock": {
                        "preset": "2500"
                    }
                }
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )


class TestPairedElevatorContingencyH3(unittest.TestCase):
    """H3 Tests: Paired inrush dampening and automatic 300s restoration."""

    def test_paired_inrush_dampener_activation(self):
        """When canary restarts, partner is temporarily stepped down to absorb L*di/dt inrush surge."""
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2700W",
        }
        now_ts = 10000.0

        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-24",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=now_ts,
            enable_paired_inrush=True,
            inrush_dampener_seconds=300.0,
        )

        self.assertEqual(decision.action, ACTION_STEP_DOWN_CANARY)
        self.assertEqual(decision.target_miner, "S19JPRO-24")
        self.assertEqual(decision.target_preset, "2500W")
        self.assertTrue(decision.requires_write)

        # Partner dampener verification
        self.assertTrue(decision.partner_requires_write)
        self.assertEqual(decision.partner_miner, "S19JPRO-23")
        self.assertEqual(decision.partner_target_preset, "2500W")

        # Group state verification
        st = decision.updated_group_state
        self.assertIsNotNone(st)
        self.assertTrue(st.active)
        self.assertTrue(st.inrush_dampener_active)
        self.assertEqual(st.inrush_dampener_expires_ts, 10300.0)
        self.assertEqual(st.inrush_dampener_partner, "S19JPRO-23")
        self.assertEqual(st.inrush_dampener_restored_preset, "2700W")
        self.assertIn("amortigua a 2500W (300s)", decision.notification_msg)

    def test_paired_inrush_disabled_backward_compatibility(self):
        """When enable_paired_inrush is False, partner is untouched."""
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2700W",
        }
        now_ts = 10000.0

        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-24",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=now_ts,
            enable_paired_inrush=False,
        )

        self.assertEqual(decision.action, ACTION_STEP_DOWN_CANARY)
        self.assertFalse(decision.partner_requires_write)
        self.assertEqual(decision.partner_miner, "")
        self.assertFalse(decision.updated_group_state.inrush_dampener_active)

    def test_inrush_dampener_not_expired_during_soak_tick(self):
        """During dampener window (<300s), soak_tick does not prematurely restore partner."""
        st = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=1,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            inrush_dampener_active=True,
            inrush_dampener_expires_ts=10300.0,
            inrush_dampener_partner="S19JPRO-23",
            inrush_dampener_restored_preset="2700W",
        )
        presets = {
            "S19JPRO-23": "2500W",
            "S19JPRO-24": "2500W",
        }

        # 120s later -> still dampening
        decision = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=10120.0,
            group_state=st,
        )

        self.assertEqual(decision.action, ACTION_NO_ACTION)
        self.assertFalse(decision.requires_write)
        self.assertTrue(decision.updated_group_state.inrush_dampener_active)

    def test_inrush_dampener_restoration_after_300s_expiry(self):
        """After 300s, soak_tick restores dampened partner back to its nominal preset."""
        st = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=1,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            inrush_dampener_active=True,
            inrush_dampener_expires_ts=10300.0,
            inrush_dampener_partner="S19JPRO-23",
            inrush_dampener_restored_preset="2700W",
        )
        presets = {
            "S19JPRO-23": "2500W",
            "S19JPRO-24": "2500W",
        }

        # 301s later -> expiry reached!
        decision = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=10301.0,
            group_state=st,
        )

        self.assertEqual(decision.action, ACTION_RESTORE_INRUSH_DAMPENER)
        self.assertEqual(decision.target_miner, "S19JPRO-23")
        self.assertEqual(decision.target_preset, "2700W")
        self.assertTrue(decision.requires_write)
        self.assertIn("AMORTIGUACIÓN DE ELEVADOR FINALIZADA", decision.notification_msg)

        # State should clear dampener but remain in contingency for canary
        new_st = decision.updated_group_state
        self.assertIsNotNone(new_st)
        self.assertTrue(new_st.active)
        self.assertFalse(new_st.inrush_dampener_active)
        self.assertIsNone(new_st.inrush_dampener_expires_ts)
        self.assertEqual(new_st.inrush_dampener_partner, "")


class TestPairedElevatorContingencyH4(unittest.TestCase):
    """H4 Tests: Fan governor thermal warmup floor & overcooling protection."""

    def setUp(self):
        self.cfg = GovernorConfig()

    def test_warmup_guard_suppresses_recovery_max_cooling(self):
        """When is_warming_up is True, RECOVERY_MAX_COOLING is suppressed even under power deficit."""
        decision = compute_governor_step(
            max_temp_c=54.0,  # Cold chips during boot!
            current_duty=75,
            seconds_since_last_change=120.0,
            target_power_w=2700.0,
            current_power_w=1200.0,  # Deficit > 200W
            config=self.cfg,
            is_warming_up=True,
        )
        # Should NOT jump to RECOVERY_MAX_COOLING (100%)
        self.assertNotEqual(decision.action, ACTION_RECOVERY_MAX_COOLING)
        # Normal cooling modulation allows chips to warm up
        self.assertIn(decision.action, (ACTION_STEP_DOWN, ACTION_HOLD_DWELL, ACTION_HOLD_TARGET))

    def test_low_power_guard_suppresses_recovery_max_cooling(self):
        """When current_power_w < 500W (pre-hashing/autotuning), RECOVERY_MAX_COOLING is suppressed."""
        decision = compute_governor_step(
            max_temp_c=52.0,
            current_duty=80,
            seconds_since_last_change=120.0,
            target_power_w=2700.0,
            current_power_w=250.0,  # Pre-hashing power
            config=self.cfg,
            is_warming_up=False,
        )
        self.assertNotEqual(decision.action, ACTION_RECOVERY_MAX_COOLING)

    def test_hashing_power_deficit_activates_recovery_max_cooling(self):
        """When stable hashing (power >= 500W, not warming up) has power deficit, 100% cooling activates."""
        decision = compute_governor_step(
            max_temp_c=74.0,
            current_duty=80,
            seconds_since_last_change=120.0,
            target_power_w=2700.0,
            current_power_w=2300.0,  # Deficit > 200W
            config=self.cfg,
            is_warming_up=False,
        )
        self.assertEqual(decision.action, ACTION_RECOVERY_MAX_COOLING)
        self.assertEqual(decision.target_duty, 100)
        self.assertTrue(decision.requires_write)

    def test_emergency_spike_overrides_warmup_guard(self):
        """Inviolable P0 Safety: Temp >= 83.0°C ALWAYS triggers EMERGENCY_SPIKE to 100% even if is_warming_up is True."""
        decision = compute_governor_step(
            max_temp_c=83.5,
            current_duty=75,
            seconds_since_last_change=10.0,
            target_power_w=2700.0,
            current_power_w=100.0,
            config=self.cfg,
            is_warming_up=True,
        )
        self.assertEqual(decision.action, ACTION_EMERGENCY_SPIKE)
        self.assertEqual(decision.target_duty, 100)
        self.assertTrue(decision.is_emergency)
        self.assertTrue(decision.requires_write)


class TestPairedElevatorContingencySerialization(unittest.TestCase):
    """Serialization roundtrip and backward compatibility tests."""

    def test_full_roundtrip_with_inrush_fields(self):
        st = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=1000.0,
            last_restart_ts=1100.0,
            step_down_count=1,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            soak_duration_seconds=7200.0,
            inrush_dampener_active=True,
            inrush_dampener_expires_ts=1400.0,
            inrush_dampener_partner="S19JPRO-23",
            inrush_dampener_restored_preset="2700W",
        )
        data = st.to_dict()
        loaded = GroupContingencyState.from_dict(data)
        self.assertEqual(st, loaded)

    def test_legacy_dict_backward_compatibility(self):
        """Loading state dictionary lacking inrush fields safely defaults to inactive."""
        legacy_data = {
            "group_name": "elevator_2",
            "active": True,
            "trigger_miner": "S19JPRO-25",
            "started_ts": 2000.0,
            "last_restart_ts": 2100.0,
            "step_down_count": 2,
            "canary_initial_preset": "2700W",
            "partner_initial_preset": "2700W",
            "soak_duration_seconds": 7200.0,
        }
        loaded = GroupContingencyState.from_dict(legacy_data)
        self.assertEqual(loaded.group_name, "elevator_2")
        self.assertTrue(loaded.active)
        self.assertFalse(loaded.inrush_dampener_active)
        self.assertIsNone(loaded.inrush_dampener_expires_ts)
        self.assertEqual(loaded.inrush_dampener_partner, "")
        self.assertIsNone(loaded.inrush_dampener_restored_preset)


if __name__ == "__main__":
    unittest.main()
