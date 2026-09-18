"""Unit tests for Elevator Budget, Settle Window & Soft-Contingency Governance (Spec 077 / PROP-012)."""

from datetime import datetime
import unittest

from app.governance.elevator_budget import (
    ACTION_ALLOW_TRANSITION,
    ACTION_HOLD_ASYMMETRY_PREFERENCE,
    ACTION_HOLD_BUDGET_LIMIT,
    ACTION_HOLD_FACILITY_SETTLE,
    ACTION_HOLD_SCHEDULE_CEILING,
    DEFAULT_FACILITY_SETTLE_WINDOW_S,
    DEFAULT_PEAK_ELEVATOR_BUDGET_W,
    DEFAULT_VALLEY_ELEVATOR_BUDGET_W,
    FacilityBudgetState,
    calculate_group_wattage,
    can_step_up_within_budget,
    evaluate_facility_transition_permission,
    evaluate_soft_contingency_schedule,
    evaluate_symmetric_balance_preference,
    parse_preset_wattage,
)


class TestFacilityBudgetState(unittest.TestCase):
    """Verifies the facility-wide transition state tracker across the shared drop line."""

    def test_initial_state_not_in_settle(self):
        st = FacilityBudgetState()
        in_settle, rem_s, active_m = st.is_facility_in_settle(1000.0)
        self.assertFalse(in_settle)
        self.assertEqual(rem_s, 0.0)
        self.assertEqual(active_m, "")

    def test_record_transition_locks_facility(self):
        st = FacilityBudgetState(settle_window_seconds=180.0)
        st.record_transition("S19JPRO-24", "2500W", now_ts=1000.0)

        # 60 seconds later: still 120s remaining
        in_settle, rem_s, active_m = st.is_facility_in_settle(1060.0)
        self.assertTrue(in_settle)
        self.assertAlmostEqual(rem_s, 120.0, places=1)
        self.assertEqual(active_m, "S19JPRO-24")

        # 181 seconds later: expired
        in_settle, rem_s, active_m = st.is_facility_in_settle(1181.0)
        self.assertFalse(in_settle)
        self.assertEqual(rem_s, 0.0)

    def test_clear_settle(self):
        st = FacilityBudgetState()
        st.record_transition("S19JPRO-25", "2500W", now_ts=500.0)
        st.clear_settle()
        in_settle, rem_s, _ = st.is_facility_in_settle(510.0)
        self.assertFalse(in_settle)
        self.assertEqual(rem_s, 0.0)

    def test_serialization_roundtrip(self):
        st = FacilityBudgetState(
            last_facility_transition_ts=12345.6,
            active_transition_miner="S19JPRO-26",
            active_transition_target_preset="2700W",
            settle_window_seconds=180.0,
        )
        d = st.to_dict()
        loaded = FacilityBudgetState.from_dict(d)
        self.assertEqual(st, loaded)


class TestSoftContingencySchedule(unittest.TestCase):
    """Verifies weekday peak windows vs off-peak and weekend valley."""

    def test_weekday_morning_peak(self):
        # Monday (2026-09-21) 09:15 AM
        dt = datetime(2026, 9, 21, 9, 15)
        eval_res = evaluate_soft_contingency_schedule(dt)
        self.assertTrue(eval_res.is_peak_window)
        self.assertEqual(eval_res.window_name, "morning_peak")
        self.assertEqual(eval_res.max_individual_preset, "2500W")
        self.assertEqual(eval_res.max_elevator_budget_w, 5000)

    def test_weekday_morning_boundaries(self):
        # Exactly 08:30 (starts)
        dt_start = datetime(2026, 9, 21, 8, 30, 0)
        self.assertTrue(evaluate_soft_contingency_schedule(dt_start).is_peak_window)

        # 08:29:59 (before start)
        dt_before = datetime(2026, 9, 21, 8, 29, 59)
        self.assertFalse(evaluate_soft_contingency_schedule(dt_before).is_peak_window)

        # Exactly 10:30 (ended)
        dt_end = datetime(2026, 9, 21, 10, 30, 0)
        self.assertFalse(evaluate_soft_contingency_schedule(dt_end).is_peak_window)

    def test_weekday_evening_peak(self):
        # Wednesday (2026-09-23) 20:45 PM
        dt = datetime(2026, 9, 23, 20, 45)
        eval_res = evaluate_soft_contingency_schedule(dt)
        self.assertTrue(eval_res.is_peak_window)
        self.assertEqual(eval_res.window_name, "evening_peak")
        self.assertEqual(eval_res.max_individual_preset, "2500W")
        self.assertEqual(eval_res.max_elevator_budget_w, 5000)

    def test_weekday_evening_boundaries(self):
        # Exactly 19:30 (starts)
        dt_start = datetime(2026, 9, 23, 19, 30, 0)
        self.assertTrue(evaluate_soft_contingency_schedule(dt_start).is_peak_window)

        # 22:30 (ended)
        dt_end = datetime(2026, 9, 23, 22, 30, 0)
        self.assertFalse(evaluate_soft_contingency_schedule(dt_end).is_peak_window)

    def test_weekday_off_peak(self):
        # Thursday 14:00 PM
        dt = datetime(2026, 9, 24, 14, 0)
        eval_res = evaluate_soft_contingency_schedule(dt)
        self.assertFalse(eval_res.is_peak_window)
        self.assertEqual(eval_res.window_name, "off_peak_weekday")
        self.assertEqual(eval_res.max_individual_preset, "2700W")
        self.assertEqual(eval_res.max_elevator_budget_w, 5400)

    def test_weekend_unrestricted_valley(self):
        # Saturday (2026-09-19) 09:00 AM (would be peak if weekday, but weekend is valley)
        dt_sat = datetime(2026, 9, 19, 9, 0)
        eval_sat = evaluate_soft_contingency_schedule(dt_sat)
        self.assertFalse(eval_sat.is_peak_window)
        self.assertEqual(eval_sat.window_name, "weekend_valley")
        self.assertEqual(eval_sat.max_individual_preset, "2700W")
        self.assertEqual(eval_sat.max_elevator_budget_w, 5400)

        # Sunday (2026-09-20) 20:00 PM
        dt_sun = datetime(2026, 9, 20, 20, 0)
        eval_sun = evaluate_soft_contingency_schedule(dt_sun)
        self.assertFalse(eval_sun.is_peak_window)
        self.assertEqual(eval_sun.window_name, "weekend_valley")


class TestElevatorBudgetCalculations(unittest.TestCase):
    """Verifies group wattage calculations and budget limit checks."""

    def test_parse_preset_wattage(self):
        self.assertEqual(parse_preset_wattage("2500W"), 2500)
        self.assertEqual(parse_preset_wattage("2700"), 2700)
        self.assertEqual(parse_preset_wattage("2300W"), 2300)
        self.assertEqual(parse_preset_wattage("1800W"), 1800)

    def test_calculate_group_wattage(self):
        presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}
        self.assertEqual(calculate_group_wattage(presets), 5000)

        asym = {"S19JPRO-25": "2300W", "S19JPRO-26": "2700W"}
        self.assertEqual(calculate_group_wattage(asym), 5000)

    def test_can_step_up_within_budget_peak_limit(self):
        presets = {"S19JPRO-23": "2300W", "S19JPRO-24": "2500W"}

        # Miner 23 stepping up 2300W -> 2500W with 5000W limit (2500 + 2500 = 5000 <= 5000)
        ok, proj_w, _ = can_step_up_within_budget(
            "S19JPRO-23", "2500W", presets, max_budget_w=5000
        )
        self.assertTrue(ok)
        self.assertEqual(proj_w, 5000)

        # Miner 24 stepping up 2500W -> 2700W with partner at 2300W (2300 + 2700 = 5000 <= 5000)
        ok_5000, proj_5000, _ = can_step_up_within_budget(
            "S19JPRO-24", "2700W", presets, max_budget_w=5000
        )
        self.assertTrue(ok_5000)
        self.assertEqual(proj_5000, 5000)

        # Partner at 2500W: stepping up 2500W -> 2700W (2500 + 2700 = 5200 > 5000)
        presets_at_5000 = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}
        ok_exceed, proj_exceed, err_msg = can_step_up_within_budget(
            "S19JPRO-24", "2700W", presets_at_5000, max_budget_w=5000
        )
        self.assertFalse(ok_exceed)
        self.assertEqual(proj_exceed, 5200)
        self.assertIn("Excede presupuesto de elevador", err_msg)


class TestSymmetricBalancePreference(unittest.TestCase):
    """Verifies priority of 2x 2500W over asymmetric 2700W + 2300W."""

    def test_blocks_2700_when_partner_below_2500(self):
        # S19JPRO-25 wants 2700W, but S19JPRO-26 is at 2300W
        presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2300W"}
        ok, reason = evaluate_symmetric_balance_preference("S19JPRO-25", "2700W", presets)
        self.assertFalse(ok)
        self.assertIn("Preferencia simétrica de elevador", reason)
        self.assertIn("S19JPRO-26", reason)

    def test_allows_2700_when_partner_at_least_2500(self):
        # S19JPRO-25 wants 2700W, and partner is at 2500W
        presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2500W"}
        ok, reason = evaluate_symmetric_balance_preference("S19JPRO-25", "2700W", presets)
        self.assertTrue(ok)
        self.assertEqual(reason, "OK")

    def test_allows_partner_to_step_up_to_2500(self):
        # Partner stepping up from 2300W -> 2500W is allowed (reaches symmetry)
        presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2300W"}
        ok, reason = evaluate_symmetric_balance_preference("S19JPRO-26", "2500W", presets)
        self.assertTrue(ok)
        self.assertEqual(reason, "OK")


class TestFacilityTransitionPermission(unittest.TestCase):
    """Comprehensive permission gate testing across drop line, schedule, and budgets."""

    def setUp(self):
        self.facility_state = FacilityBudgetState()
        self.off_peak_dt = datetime(2026, 9, 21, 14, 0)   # Monday 14:00 (off-peak)
        self.peak_dt = datetime(2026, 9, 21, 9, 0)        # Monday 09:00 (peak)

    def test_emergency_step_down_always_allowed(self):
        # Even if another miner recently changed preset (facility in settle)
        self.facility_state.record_transition("S19JPRO-24", "2500W", now_ts=1000.0)
        group_presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-25",
            current_preset="2500W",
            target_preset="2300W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=1030.0,  # 30s into settle window!
            facility_state=self.facility_state,
            now_dt=self.off_peak_dt,
            is_step_down=True,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)
        self.assertIn("Desescalada permitida", dec.reason)

    def test_step_up_blocked_by_facility_settle_window(self):
        # S19JPRO-24 stepped up at t=1000. S19JPRO-26 wants to step up at t=1060 (60s later)
        self.facility_state.record_transition("S19JPRO-24", "2500W", now_ts=1000.0)
        group_presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2300W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-26",
            current_preset="2300W",
            target_preset="2500W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=1060.0,
            facility_state=self.facility_state,
            now_dt=self.off_peak_dt,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_FACILITY_SETTLE)
        self.assertAlmostEqual(dec.remaining_settle_seconds, 120.0, places=1)
        self.assertIn("Bajada compartida en estabilización", dec.reason)

    def test_step_up_blocked_by_peak_schedule_ceiling(self):
        # Monday 09:00 AM (peak window): attempt to step up to 2700W is rejected
        group_presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-25",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=2000.0,
            facility_state=self.facility_state,
            now_dt=self.peak_dt,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_SCHEDULE_CEILING)
        self.assertIn("Límite de soft-contingencia horaria activo", dec.reason)

    def test_step_up_blocked_by_asymmetry_preference(self):
        # Off-peak, but partner is at 2300W -> trying to step up to 2700W rejected
        group_presets = {"S19JPRO-23": "2300W", "S19JPRO-24": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=3000.0,
            facility_state=self.facility_state,
            now_dt=self.off_peak_dt,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_ASYMMETRY_PREFERENCE)
        self.assertIn("Preferencia simétrica de elevador", dec.reason)

    def test_step_up_allowed_off_peak_with_symmetry(self):
        # Off-peak, partner at 2500W, candidate at 2500W -> step up to 2700W allowed (5200W <= 5400W)
        group_presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=4000.0,
            facility_state=self.facility_state,
            now_dt=self.off_peak_dt,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)
        self.assertEqual(dec.projected_group_power_w, 5200)


if __name__ == "__main__":
    unittest.main()
