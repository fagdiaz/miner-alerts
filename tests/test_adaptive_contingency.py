"""Unit tests for Adaptive Elevator Contingency & Canary Throttle (Spec 057)."""

import unittest
from app.governance.adaptive_contingency import (
    ACTION_HOLD_CONTINGENCY,
    ACTION_NO_ACTION,
    ACTION_RESTORE_NOMINAL,
    ACTION_STEP_DOWN_CANARY,
    ACTION_STEP_DOWN_LIMIT,
    ACTION_STEP_DOWN_PARTNER,
    ACTION_STEP_UP_SOAK,
    DEFAULT_CANARY_MAP,
    GroupContingencyState,
    evaluate_canary_contingency,
    find_next_preset_tier,
    find_previous_preset_tier,
    is_canary_miner,
    normalize_miner_name,
)


class TestAdaptiveContingencyPolicy(unittest.TestCase):
    def test_miner_normalization_and_canary_detection(self):
        self.assertEqual(normalize_miner_name("24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("Miner 24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("S19JPRO-24"), "S19JPRO-24")
        self.assertEqual(normalize_miner_name("S19j Pro 25"), "S19JPRO-25")

        # Check elevator_1 default canary (Miner 24)
        self.assertTrue(is_canary_miner("S19JPRO-24", "elevator_1"))
        self.assertTrue(is_canary_miner("24", "elevator_1"))
        self.assertFalse(is_canary_miner("S19JPRO-23", "elevator_1"))

        # Check elevator_2 default canary (Miner 25)
        self.assertTrue(is_canary_miner("S19JPRO-25", "elevator_2"))
        self.assertFalse(is_canary_miner("S19JPRO-26", "elevator_2"))

    def test_preset_tier_transitions(self):
        # Stepping down
        self.assertEqual(find_previous_preset_tier("2700W"), "2500W")
        self.assertEqual(find_previous_preset_tier("2500W"), "2300W")
        self.assertEqual(find_previous_preset_tier("2300W"), "2150W")
        self.assertIsNone(find_previous_preset_tier("2150W"), "Should hit default floor of 2150W")

        # Stepping down with custom lower floor
        self.assertEqual(find_previous_preset_tier("1850W", min_floor="1740W"), "1800W")
        self.assertEqual(find_previous_preset_tier("1800W", min_floor="1740W"), "1740W")
        self.assertIsNone(find_previous_preset_tier("1740W", min_floor="1740W"))

        # Stepping up
        self.assertEqual(find_next_preset_tier("1800W"), "1850W")
        self.assertEqual(find_next_preset_tier("2150W"), "2300W")
        self.assertEqual(find_next_preset_tier("2300W"), "2500W")
        self.assertEqual(find_next_preset_tier("2500W"), "2700W")
        self.assertIsNone(find_next_preset_tier("2700W"), "Should hit default ceiling of 2700W")

    def test_initial_canary_restart_asymmetric_reduction(self):
        """User Story 3: Initial canary restart reduces ONLY canary by 1 tier relative to current state."""
        presets = {
            "S19JPRO-23": "2500W",  # Partner is already at 2500W
            "S19JPRO-24": "2700W",  # Canary is at 2700W
        }
        now_ts = 10000.0

        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-24",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=now_ts,
        )

        self.assertEqual(decision.action, ACTION_STEP_DOWN_CANARY)
        self.assertEqual(decision.target_miner, "S19JPRO-24")
        self.assertEqual(decision.previous_preset, "2700W")
        self.assertEqual(decision.target_preset, "2500W")
        self.assertTrue(decision.requires_write)
        self.assertIn("CONTINGENCIA ASIMÉTRICA", decision.notification_msg)
        self.assertIn("S19JPRO-23 se mantiene en 2500W", decision.notification_msg)

        # Verify state transition
        st = decision.updated_group_state
        self.assertIsNotNone(st)
        self.assertTrue(st.active)
        self.assertEqual(st.trigger_miner, "S19JPRO-24")
        self.assertEqual(st.step_down_count, 1)
        self.assertEqual(st.canary_initial_preset, "2700W")
        self.assertEqual(st.partner_initial_preset, "2500W")

    def test_limit_exploration_canary_second_restart(self):
        """User Story 4: If canary restarts again at reduced power, explores next limit down."""
        # Initial state already in contingency
        init_state = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=1,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
        )
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2500W",  # Canary is now at 2500W
        }
        now_ts = 10600.0  # 10 min later

        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-24",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=now_ts,
            group_state=init_state,
        )

        self.assertEqual(decision.action, ACTION_STEP_DOWN_LIMIT)
        self.assertEqual(decision.target_miner, "S19JPRO-24")
        self.assertEqual(decision.previous_preset, "2500W")
        self.assertEqual(decision.target_preset, "2300W")
        self.assertTrue(decision.requires_write)
        self.assertIn("PRUEBA EN LOS LÍMITES", decision.notification_msg)
        self.assertEqual(decision.updated_group_state.step_down_count, 2)

    def test_canary_floor_reached_holds_contingency(self):
        """Canary reaches 2150W floor and cannot be reduced further."""
        init_state = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            step_down_count=3,
            canary_initial_preset="2700W",
        )
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2150W",
        }
        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-24",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=11000.0,
            group_state=init_state,
        )
        self.assertEqual(decision.action, ACTION_HOLD_CONTINGENCY)
        self.assertFalse(decision.requires_write)

    def test_robust_partner_restart_reduces_partner(self):
        """When the robust partner restarts under severe perturbation, it also steps down."""
        init_state = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            step_down_count=1,
        )
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2500W",
        }
        decision = evaluate_canary_contingency(
            event_type="unexpected_restart",
            miner_name="S19JPRO-23",  # Partner restarts!
            group_name="elevator_1",
            current_presets=presets,
            now_ts=10500.0,
            group_state=init_state,
        )

        self.assertEqual(decision.action, ACTION_STEP_DOWN_PARTNER)
        self.assertEqual(decision.target_miner, "S19JPRO-23")
        self.assertEqual(decision.previous_preset, "2700W")
        self.assertEqual(decision.target_preset, "2500W")
        self.assertTrue(decision.requires_write)
        self.assertIn("MINERO ROBUSTO", decision.notification_msg)

    def test_step_up_soak_recovery_after_2_hours(self):
        """User Story 4: 2 hours without restarts triggers step-up soak and eventual nominal restore."""
        init_state = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=2,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            soak_duration_seconds=7200.0,
        )
        presets = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2300W",
        }

        # Case 1: Only 1 hour elapsed (no action yet)
        dec_1h = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=13600.0,  # 3600s elapsed
            group_state=init_state,
        )
        self.assertEqual(dec_1h.action, ACTION_NO_ACTION)

        # Case 2: 2 hours elapsed (7201s) -> Step up canary 2300W -> 2500W
        dec_2h = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=17201.0,
            group_state=init_state,
        )
        self.assertEqual(dec_2h.action, ACTION_STEP_UP_SOAK)
        self.assertEqual(dec_2h.target_miner, "S19JPRO-24")
        self.assertEqual(dec_2h.previous_preset, "2300W")
        self.assertEqual(dec_2h.target_preset, "2500W")
        self.assertTrue(dec_2h.requires_write)
        self.assertTrue(dec_2h.updated_group_state.active)

        # Case 3: Another 2 hours elapsed -> Step up canary 2500W -> 2700W (RESTORE_NOMINAL)
        presets_after = {
            "S19JPRO-23": "2700W",
            "S19JPRO-24": "2500W",
        }
        dec_4h = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets_after,
            now_ts=24402.0,
            group_state=dec_2h.updated_group_state,
        )
        self.assertEqual(dec_4h.action, ACTION_RESTORE_NOMINAL)
        self.assertEqual(dec_4h.target_miner, "S19JPRO-24")
        self.assertEqual(dec_4h.target_preset, "2700W")
        self.assertFalse(dec_4h.updated_group_state.active, "Group should return to nominal inactive state")

    def test_soak_tick_recovers_robust_partner_when_canary_nominal(self):
        """When only the robust partner was stepped down, soak tick steps up the partner without touching canary."""
        st = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-23",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=1,
            canary_initial_preset=None,  # Canary was never degraded
            partner_initial_preset="2700W",
            soak_duration_seconds=7200.0,
        )
        presets = {
            "S19JPRO-23": "2500W",
            "S19JPRO-24": "2700W",  # Canary is already nominal
        }
        dec = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets,
            now_ts=17201.0,
            group_state=st,
        )
        self.assertEqual(dec.action, ACTION_RESTORE_NOMINAL)
        self.assertEqual(dec.target_miner, "S19JPRO-23")
        self.assertEqual(dec.previous_preset, "2500W")
        self.assertEqual(dec.target_preset, "2700W")
        self.assertTrue(dec.requires_write)
        self.assertFalse(dec.updated_group_state.active)

    def test_soak_tick_sequential_dual_recovery(self):
        """When both canary and partner are stepped down, they recover sequentially and state stays active until both finish."""
        st = GroupContingencyState(
            group_name="elevator_1",
            active=True,
            trigger_miner="S19JPRO-24",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=2,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            soak_duration_seconds=7200.0,
        )
        presets_initial = {
            "S19JPRO-23": "2500W",
            "S19JPRO-24": "2500W",
        }
        # First soak tick: steps up canary
        dec_1 = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets_initial,
            now_ts=17201.0,
            group_state=st,
        )
        self.assertEqual(dec_1.action, ACTION_STEP_UP_SOAK)
        self.assertEqual(dec_1.target_miner, "S19JPRO-24")
        self.assertEqual(dec_1.target_preset, "2700W")
        self.assertTrue(dec_1.updated_group_state.active, "Must remain active because partner is still degraded")

        # Second soak tick: canary is nominal (2700W), partner steps up
        presets_second = {
            "S19JPRO-23": "2500W",
            "S19JPRO-24": "2700W",
        }
        dec_2 = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_1",
            current_presets=presets_second,
            now_ts=24402.0,
            group_state=dec_1.updated_group_state,
        )
        self.assertEqual(dec_2.action, ACTION_RESTORE_NOMINAL)
        self.assertEqual(dec_2.target_miner, "S19JPRO-23")
        self.assertEqual(dec_2.target_preset, "2700W")
        self.assertFalse(dec_2.updated_group_state.active, "Now both are nominal, group returns to inactive")

    def test_serialization_roundtrip(self):
        st = GroupContingencyState(
            group_name="elevator_2",
            active=True,
            trigger_miner="S19JPRO-25",
            started_ts=5000.0,
            last_restart_ts=5100.0,
            step_down_count=1,
            canary_initial_preset="2700W",
            partner_initial_preset="2700W",
            soak_duration_seconds=7200.0,
        )
        d = st.to_dict()
        loaded = GroupContingencyState.from_dict(d)
        self.assertEqual(st, loaded)

    def test_soak_recovery_with_low_initial_preset_and_symmetric_choice(self):
        """Verify that when initial presets were degraded (<2500W), soak recovery targets 2500W floor and picks lowest miner first."""
        # Elevator 2 with both miners degraded to 2150W and 2000W
        init_state = GroupContingencyState(
            group_name="elevator_2",
            active=True,
            trigger_miner="S19JPRO-25",
            started_ts=10000.0,
            last_restart_ts=10000.0,
            step_down_count=2,
            canary_initial_preset="2150W",
            partner_initial_preset="2150W",
            soak_duration_seconds=7200.0,
        )
        presets = {
            "S19JPRO-25": "2150W",  # Canary
            "S19JPRO-26": "2000W",  # Partner (lower!)
        }
        # Soak tick after 2h: partner is lowest (2000W vs 2150W), so partner must step up to 2150W!
        dec_1 = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_2",
            current_presets=presets,
            now_ts=17201.0,
            group_state=init_state,
        )
        self.assertEqual(dec_1.action, ACTION_STEP_UP_SOAK)
        self.assertEqual(dec_1.target_miner, "S19JPRO-26")
        self.assertEqual(dec_1.target_preset, "2150W")
        self.assertTrue(dec_1.updated_group_state.active)

        # Both at 2500W: contingency must complete and active must become False
        presets_nominal = {
            "S19JPRO-25": "2500W",
            "S19JPRO-26": "2500W",
        }
        dec_done = evaluate_canary_contingency(
            event_type="soak_tick",
            miner_name="",
            group_name="elevator_2",
            current_presets=presets_nominal,
            now_ts=30000.0,
            group_state=dec_1.updated_group_state,
        )
        self.assertEqual(dec_done.action, ACTION_RESTORE_NOMINAL)
        self.assertFalse(dec_done.updated_group_state.active)


if __name__ == "__main__":
    unittest.main()

