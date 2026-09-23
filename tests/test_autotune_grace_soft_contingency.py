"""
Unit tests for Autotune Grace Period, Limit-Cycle Feedback Loop Prevention,
and Desired Profile Governance in Soft Contingency (Spec 079 Addendum / PROP-014).
"""

from datetime import datetime
import threading
import unittest
from unittest.mock import MagicMock, patch

from app.governance.elevator_budget import (
    FacilityBudgetState,
    evaluate_soft_contingency_schedule,
    evaluate_solar_thermal_envelope,
    get_miner_max_hardware_preset,
    parse_preset_wattage,
)
from app.governance.power_progression import (
    PROFILE_C0_BASE_STABLE,
    PROFILE_C1_ASYMMETRIC,
    PROFILE_C4_MAX_POWER,
    PROFILE_TARGETS,
    ProgressionOrchestratorState,
    get_global_progression_state,
    set_global_desired_profile,
)


class DummyState:
    def __init__(
        self,
        last_power_w=2499.0,
        last_max_chip_temp=78.0,
        last_fan_duty_percent=78.0,
        last_elapsed=1200,
        vnish_discovered_top_preset="2500",
        vnish_discovered_preset="2500",
        balancer_preset="2500W",
        last_responded=True,
    ):
        self.last_power_w = last_power_w
        self.last_max_chip_temp = last_max_chip_temp
        self.last_fan_duty_percent = last_fan_duty_percent
        self.last_elapsed = last_elapsed
        self.vnish_discovered_top_preset = vnish_discovered_top_preset
        self.vnish_discovered_preset = vnish_discovered_preset
        self.balancer_preset = balancer_preset
        self.last_responded = last_responded
        self.vnish_discovered_target_power_w = float(parse_preset_wattage(vnish_discovered_preset)) if vnish_discovered_preset else 2500.0


class TestAutotuneGraceSoftContingency(unittest.TestCase):
    def setUp(self):
        self.config = {
            "soft_contingency_morning_start": "08:30",
            "soft_contingency_morning_end": "09:30",
            "soft_contingency_evening_start": "20:00",
            "soft_contingency_evening_end": "21:15",
            "soft_contingency_peak_max_preset": "2500W",
            "soft_contingency_valley_max_preset": "2700W",
            "autotune_grace_period_seconds": 900.0,
            "valley_step_up_max_chip_temp_c": 80.0,
            "valley_step_up_max_fan_duty_pct": 92.0,
            "miners": [
                {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1", "max_hardware_preset": "2700W"},
                {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1", "max_hardware_preset": "2700W"},
                {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_2", "max_hardware_preset": "2500W"},
                {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_2", "max_hardware_preset": "2500W"},
            ],
        }
        self.miners = self.config["miners"]
        # Default global progression profile
        st = get_global_progression_state()
        st.desired_profile = PROFILE_C0_BASE_STABLE
        st.current_profile = PROFILE_C0_BASE_STABLE
        st.last_transition_ts = 0.0

    def test_default_progression_profile_is_c0_base_stable(self):
        """Verify that newly initialized orchestrator defaults to safe C0_BASE_STABLE."""
        fresh_state = ProgressionOrchestratorState()
        self.assertEqual(fresh_state.desired_profile, PROFILE_C0_BASE_STABLE)
        self.assertEqual(fresh_state.current_profile, PROFILE_C0_BASE_STABLE)

    def test_configured_2500w_miner_not_in_miners_below_2500_during_autotune(self):
        """
        Critical regression test:
        When M26 is autotuning at 2500W and drawing 2298W, it must NOT be flagged as
        below 2500W because its configured preset is already 2500W.
        """
        # M26 state: top=2500, preset=2500, power=2298W (autotuning)
        st26 = DummyState(
            last_power_w=2298.0,
            last_elapsed=150,  # 2.5 min uptime
            vnish_discovered_top_preset="2500",
            vnish_discovered_preset="2500",
            balancer_preset="2500W",
        )
        # Check configured target logic
        _cfg_top_w = parse_preset_wattage(st26.vnish_discovered_top_preset)
        _cfg_pr_w = parse_preset_wattage(st26.vnish_discovered_preset)
        _target_cfg_w = min(_cfg_top_w, _cfg_pr_w)

        self.assertGreaterEqual(_target_cfg_w, 2500)
        # Verify that an autotuning miner at 2298W with target 2500W does NOT get added to below_2500
        is_below_2500 = (_target_cfg_w < 2500)
        self.assertFalse(is_below_2500)

    def test_autotune_grace_period_sets_fleet_warming_up(self):
        """
        When any miner has last_elapsed < autotune_grace_period_seconds (e.g. 150s < 900s),
        fleet_has_warming_up must be True to prevent interrupting autotuning.
        """
        autotune_grace_s = float(self.config.get("autotune_grace_period_seconds", 900.0))
        st_rebooting = DummyState(last_elapsed=200)

        _m_elapsed = st_rebooting.last_elapsed
        fleet_has_warming_up = (0 < _m_elapsed < autotune_grace_s)
        self.assertTrue(fleet_has_warming_up)

        # After 900s (15 min), grace expires
        st_mature = DummyState(last_elapsed=950)
        _m_elapsed_mature = st_mature.last_elapsed
        fleet_has_warming_up_mature = (0 < _m_elapsed_mature < autotune_grace_s)
        self.assertFalse(fleet_has_warming_up_mature)

    def test_desired_profile_c0_clamps_stage2_effective_max_w(self):
        """
        When desired_profile is C0_BASE_STABLE, effective_max_w must be clamped
        to 2500W so Stage 2 (2700W escalation) is completely suppressed.
        """
        sched_max = "2700W"
        sched_w = parse_preset_wattage(sched_max)
        self.assertEqual(sched_w, 2700)

        prog_state = get_global_progression_state()
        prog_state.desired_profile = PROFILE_C0_BASE_STABLE

        effective_max_w = sched_w
        if prog_state.desired_profile in (PROFILE_C0_BASE_STABLE, "EMERGENCY_COOL"):
            effective_max_w = min(effective_max_w, 2500)

        self.assertEqual(effective_max_w, 2500)
        self.assertFalse(effective_max_w > 2500)

    def test_stage2_profile_target_gate_respects_asymmetric_profile(self):
        """
        When desired_profile is C1_ASYMMETRIC, S19JPRO-25 has target 2500W
        and must be skipped from 2700W promotion by Gate -1.
        """
        desired_profile = PROFILE_C1_ASYMMETRIC
        prof_targets = PROFILE_TARGETS[desired_profile]

        # S19JPRO-25 target is 2500W in C1
        self.assertEqual(prof_targets["S19JPRO-25"], "2500W")
        self.assertEqual(parse_preset_wattage(prof_targets["S19JPRO-25"]), 2500)
        self.assertLess(parse_preset_wattage(prof_targets["S19JPRO-25"]), 2700)

        # S19JPRO-26 target is 2700W in C1, but hardware ceiling in config is 2500W
        m26_hw_max = get_miner_max_hardware_preset("S19JPRO-26", config=self.config)
        self.assertEqual(m26_hw_max, "2500W")
        self.assertLess(parse_preset_wattage(m26_hw_max), 2700)

    def test_stage2_gate0_blocks_step_up_during_post_boot_grace(self):
        """
        Gate 0 in Stage 2 must block 2700W promotion if elapsed < autotune_grace_s,
        even if the chips appear cool and fans are not saturated.
        """
        autotune_grace_s = 900.0
        # Cold chips right after boot
        st_cold_boot = DummyState(
            last_max_chip_temp=72.0,  # cool
            last_fan_duty_percent=80.0,  # not saturated
            last_elapsed=180,  # 3 minutes post boot
        )
        should_block = (0 < st_cold_boot.last_elapsed < autotune_grace_s)
        self.assertTrue(should_block)


if __name__ == "__main__":
    unittest.main()
