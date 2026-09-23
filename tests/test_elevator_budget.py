"""Unit tests for Elevator Budget, Settle Window & Soft-Contingency Governance (Spec 077 / PROP-012)."""

from datetime import datetime
import unittest

from app.governance.elevator_budget import (
    ACTION_ALLOW_TRANSITION,
    ACTION_HOLD_ASYMMETRY_PREFERENCE,
    ACTION_HOLD_BUDGET_LIMIT,
    ACTION_HOLD_FACILITY_SETTLE,
    ACTION_HOLD_HARDWARE_LIMIT,
    ACTION_HOLD_INCIDENT_QUIET,
    ACTION_HOLD_SCHEDULE_CEILING,
    ACTION_HOLD_SOLAR_ENVELOPE,
    ACTION_HOLD_THERMAL_HEADROOM,
    DEFAULT_FACILITY_SETTLE_WINDOW_S,
    DEFAULT_INCIDENT_QUIET_WINDOW_S,
    DEFAULT_PEAK_ELEVATOR_BUDGET_W,
    DEFAULT_VALLEY_ELEVATOR_BUDGET_W,
    FacilityBudgetState,
    calculate_group_wattage,
    can_step_up_within_budget,
    evaluate_facility_transition_permission,
    evaluate_soft_contingency_schedule,
    evaluate_solar_thermal_envelope,
    evaluate_symmetric_balance_preference,
    get_miner_max_hardware_preset,
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

    def test_configurable_schedule(self):
        # Custom tightened config: evening peak 20:00 to 21:15
        cfg = {
            "soft_contingency_morning_start": "08:30",
            "soft_contingency_morning_end": "09:30",
            "soft_contingency_evening_start": "20:00",
            "soft_contingency_evening_end": "21:15",
            "soft_contingency_peak_max_preset": "2500W",
            "soft_contingency_valley_max_preset": "2700W",
        }
        # Monday 19:45 (outside custom peak 20:00-21:15) -> off_peak
        dt_1945 = datetime(2026, 9, 21, 19, 45)
        eval_1945 = evaluate_soft_contingency_schedule(dt_1945, config=cfg)
        self.assertFalse(eval_1945.is_peak_window)
        self.assertEqual(eval_1945.window_name, "off_peak_weekday")
        self.assertEqual(eval_1945.max_individual_preset, "2700W")

        # Monday 20:30 (inside custom peak) -> evening_peak
        dt_2030 = datetime(2026, 9, 21, 20, 30)
        eval_2030 = evaluate_soft_contingency_schedule(dt_2030, config=cfg)
        self.assertTrue(eval_2030.is_peak_window)
        self.assertEqual(eval_2030.window_name, "evening_peak")
        self.assertEqual(eval_2030.max_individual_preset, "2500W")

        # Monday 21:20 (after custom peak ended at 21:15) -> off_peak
        dt_2120 = datetime(2026, 9, 21, 21, 20)
        eval_2120 = evaluate_soft_contingency_schedule(dt_2120, config=cfg)
        self.assertFalse(eval_2120.is_peak_window)
        self.assertEqual(eval_2120.window_name, "off_peak_weekday")
        self.assertEqual(eval_2120.max_individual_preset, "2700W")


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
        self.off_peak_dt = datetime(2026, 9, 21, 23, 0)   # Monday 23:00 (off-peak night, outside solar window)
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


class TestIncidentQuietWindow(unittest.TestCase):
    """Verifies the 300s post-incident stabilization window per elevator group (PROP-013 / Spec 078)."""

    def test_record_group_incident_locks_group_for_300s(self):
        st = FacilityBudgetState(incident_quiet_window_s=300.0)
        st.record_group_incident("elevator_2", now_ts=1000.0)

        # 100s later: still in quiet (200s remaining)
        in_quiet, rem_s = st.is_group_in_incident_quiet("elevator_2", now_ts=1100.0)
        self.assertTrue(in_quiet)
        self.assertAlmostEqual(rem_s, 200.0, places=1)

        # 301s later: expired
        in_quiet, rem_s = st.is_group_in_incident_quiet("elevator_2", now_ts=1301.0)
        self.assertFalse(in_quiet)
        self.assertEqual(rem_s, 0.0)

    def test_incident_quiet_isolates_unaffected_group(self):
        st = FacilityBudgetState()
        st.record_group_incident("elevator_2", now_ts=1000.0)

        # elevator_2 is in quiet
        in_quiet_2, _ = st.is_group_in_incident_quiet("elevator_2", now_ts=1050.0)
        self.assertTrue(in_quiet_2)

        # elevator_1 is NOT in quiet
        in_quiet_1, rem_1 = st.is_group_in_incident_quiet("elevator_1", now_ts=1050.0)
        self.assertFalse(in_quiet_1)
        self.assertEqual(rem_1, 0.0)

    def test_clear_group_incident(self):
        st = FacilityBudgetState()
        st.record_group_incident("elevator_2", now_ts=1000.0)
        st.clear_group_incident("elevator_2")
        in_quiet, _ = st.is_group_in_incident_quiet("elevator_2", now_ts=1010.0)
        self.assertFalse(in_quiet)

    def test_serialization_with_incidents(self):
        st = FacilityBudgetState(
            last_facility_transition_ts=500.0,
            incident_quiet_window_s=300.0,
        )
        st.record_group_incident("elevator_1", now_ts=450.0)
        st.record_group_incident("elevator_2", now_ts=480.0)

        d = st.to_dict()
        loaded = FacilityBudgetState.from_dict(d)
        self.assertEqual(loaded.last_group_incident_ts["elevator_1"], 450.0)
        self.assertEqual(loaded.last_group_incident_ts["elevator_2"], 480.0)
        self.assertEqual(loaded.incident_quiet_window_s, 300.0)


class TestSolarThermalEnvelope(unittest.TestCase):
    """Verifies solar midday envelope clamping to 2500W and overheat relief (PROP-013 / Spec 078)."""

    def test_solar_window_midday_caps_at_2500(self):
        # 14:00 (midday solar window)
        dt = datetime(2026, 9, 21, 14, 0)
        eval_res = evaluate_solar_thermal_envelope(dt, max_chip_temp_c=78.0)
        self.assertTrue(eval_res.is_solar_window)
        self.assertFalse(eval_res.is_overheated)
        self.assertEqual(eval_res.max_authorized_preset, "2500W")
        self.assertIn("Franja solar activa", eval_res.reason)

    def test_solar_window_overheat_reason(self):
        # 14:00 with chip temp >= 82.0°C
        dt = datetime(2026, 9, 21, 14, 0)
        eval_res = evaluate_solar_thermal_envelope(dt, max_chip_temp_c=82.5)
        self.assertTrue(eval_res.is_solar_window)
        self.assertTrue(eval_res.is_overheated)
        self.assertEqual(eval_res.max_authorized_preset, "2500W")
        self.assertIn("Franja solar crítica", eval_res.reason)
        self.assertIn("82.5°C >= 82.0°C", eval_res.reason)

    def test_outside_solar_window_allows_2700(self):
        # 18:30 (outside 11:00-17:00 hs)
        dt = datetime(2026, 9, 21, 18, 30)
        eval_res = evaluate_solar_thermal_envelope(dt, max_chip_temp_c=77.0)
        self.assertFalse(eval_res.is_solar_window)
        self.assertEqual(eval_res.max_authorized_preset, "2700W")
        self.assertIn("Fuera de franja solar", eval_res.reason)

    def test_boundary_times(self):
        # 11:00:00 starts solar window
        self.assertTrue(evaluate_solar_thermal_envelope(datetime(2026, 9, 21, 11, 0, 0)).is_solar_window)
        # 10:59:59 before solar window
        self.assertFalse(evaluate_solar_thermal_envelope(datetime(2026, 9, 21, 10, 59, 59)).is_solar_window)
        # 17:00:00 ends solar window
        self.assertFalse(evaluate_solar_thermal_envelope(datetime(2026, 9, 21, 17, 0, 0)).is_solar_window)


class TestHardwareSiliconLimit(unittest.TestCase):
    """Verifies per-miner hardware silicon ceiling clamping (PROP-013 / Spec 078)."""

    def test_get_miner_max_hardware_preset_from_miners_list(self):
        cfg = {
            "miners": [
                {"name": "S19JPRO-23", "ip": "192.168.100.23", "max_hardware_preset": "2700W"},
                {"name": "S19JPRO-25", "ip": "192.168.100.25", "max_hardware_preset": "2500W"},
            ]
        }
        self.assertEqual(get_miner_max_hardware_preset("S19JPRO-23", config=cfg), "2700W")
        self.assertEqual(get_miner_max_hardware_preset("25", config=cfg), "2500W")
        self.assertEqual(get_miner_max_hardware_preset("192.168.100.25", config=cfg), "2500W")
        # Unspecified miner gets default
        self.assertEqual(get_miner_max_hardware_preset("S19JPRO-24", config=cfg), "2700W")

    def test_get_miner_max_hardware_preset_from_map(self):
        cfg = {
            "miner_hardware_limits": {
                "25": "2500W",
                "S19JPRO-26": "2700W"
            }
        }
        self.assertEqual(get_miner_max_hardware_preset("S19JPRO-25", config=cfg), "2500W")
        self.assertEqual(get_miner_max_hardware_preset("26", config=cfg), "2700W")
        self.assertEqual(get_miner_max_hardware_preset("24", config=cfg), "2700W")


class TestFacilityTransitionPermissionSpec078(unittest.TestCase):
    """Verifies integration of incident quiet, hardware limit, and solar gates in evaluate_facility_transition_permission."""

    def setUp(self):
        self.facility_state = FacilityBudgetState()
        self.night_dt = datetime(2026, 9, 21, 23, 0)     # Night off-peak
        self.solar_dt = datetime(2026, 9, 21, 13, 30)    # Midday solar window
        self.cfg = {
            "miners": [
                {"name": "S19JPRO-23", "ip": "192.168.100.23", "max_hardware_preset": "2700W"},
                {"name": "S19JPRO-24", "ip": "192.168.100.24", "max_hardware_preset": "2700W"},
                {"name": "S19JPRO-25", "ip": "192.168.100.25", "max_hardware_preset": "2500W"},
                {"name": "S19JPRO-26", "ip": "192.168.100.26", "max_hardware_preset": "2700W"},
            ]
        }

    def test_incident_quiet_window_blocks_step_up_for_affected_elevator(self):
        # Elevator 2 suffered an incident 60s ago
        self.facility_state.record_group_incident("elevator_2", now_ts=1000.0)
        group_presets = {"S19JPRO-25": "2300W", "S19JPRO-26": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-25",
            current_preset="2300W",
            target_preset="2500W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=1060.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_INCIDENT_QUIET)
        self.assertIn("reposo post-incidente", dec.reason)
        self.assertAlmostEqual(dec.remaining_settle_seconds, 240.0, places=0)

    def test_incident_quiet_does_not_block_unaffected_elevator(self):
        # Elevator 2 suffered an incident, Elevator 1 attempts step-up
        self.facility_state.record_group_incident("elevator_2", now_ts=1000.0)
        group_presets = {"S19JPRO-23": "2300W", "S19JPRO-24": "2300W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-23",
            current_preset="2300W",
            target_preset="2500W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=1060.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)

    def test_hardware_ceiling_blocks_step_up_for_miner_25(self):
        # S19JPRO-25 is at 2500W and attempts to step up to 2700W at night
        group_presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-25",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=2000.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_HARDWARE_LIMIT)
        self.assertIn("Límite de silicio de hardware individual", dec.reason)
        self.assertIn("2500W", dec.reason)

    def test_partner_can_step_up_to_2700_when_miner_25_is_at_2500(self):
        # S19JPRO-26 attempts 2700W while partner S19JPRO-25 is at 2500W (5200W <= 5400W)
        group_presets = {"S19JPRO-25": "2500W", "S19JPRO-26": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-26",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_2",
            group_presets=group_presets,
            now_ts=2000.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)
        self.assertEqual(dec.projected_group_power_w, 5200)

    def test_solar_envelope_blocks_step_up_to_2700_at_midday(self):
        # At 13:30 hs, S19JPRO-24 wants to go to 2700W
        group_presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=3000.0,
            facility_state=self.facility_state,
            now_dt=self.solar_dt,
            config=self.cfg,
            max_chip_temp_c=79.0,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_SOLAR_ENVELOPE)
        self.assertIn("Límite térmico solar activo", dec.reason)

    def test_solar_envelope_allows_step_up_to_2500_at_midday(self):
        # At 13:30 hs, S19JPRO-24 stepping up from 2300W to 2500W is allowed!
        group_presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2300W"}

        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2300W",
            target_preset="2500W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=3000.0,
            facility_state=self.facility_state,
            now_dt=self.solar_dt,
            config=self.cfg,
            max_chip_temp_c=77.0,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)
        self.assertEqual(dec.projected_group_power_w, 5000)

    def test_thermal_headroom_blocks_step_up_to_2700_when_hot(self):
        # At night (outside solar window), S19JPRO-24 wants 2700W, but chip is 81.5°C >= 80.0°C
        group_presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}
        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=4000.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
            max_chip_temp_c=81.5,
        )
        self.assertFalse(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_HOLD_THERMAL_HEADROOM)
        self.assertIn("Margen térmico insuficiente", dec.reason)

    def test_thermal_headroom_allows_step_up_to_2700_when_cool(self):
        # At night, S19JPRO-24 wants 2700W, chip is cooled to 77.0°C < 80.0°C
        group_presets = {"S19JPRO-23": "2500W", "S19JPRO-24": "2500W"}
        dec = evaluate_facility_transition_permission(
            miner_name="S19JPRO-24",
            current_preset="2500W",
            target_preset="2700W",
            group_name="elevator_1",
            group_presets=group_presets,
            now_ts=4000.0,
            facility_state=self.facility_state,
            now_dt=self.night_dt,
            config=self.cfg,
            max_chip_temp_c=77.0,
        )
        self.assertTrue(dec.can_proceed)
        self.assertEqual(dec.action, ACTION_ALLOW_TRANSITION)
        self.assertEqual(dec.projected_group_power_w, 5200)


class TestWattageResolverAndGovernancePermissions(unittest.TestCase):
    """Verifies electrical power ground truth resolution and intervention governance gating."""

    def test_wattage_resolver_ground_truth_power(self):
        # Simulates _get_miner_wattage logic
        def resolve_wattage(last_power_w, cached_preset, m_resp=True):
            w_pr = parse_preset_wattage(cached_preset)
            w_eff = w_pr
            if not m_resp or (last_power_w is not None and last_power_w < 500):
                return 0
            if last_power_w and last_power_w >= 500:
                if last_power_w >= 2600:
                    w_eff = 2700
                elif last_power_w >= 2400:
                    w_eff = 2500
                elif last_power_w >= 2200:
                    w_eff = 2300
                elif last_power_w >= 1900:
                    w_eff = 2000
                elif last_power_w >= 1700:
                    w_eff = 1800
                else:
                    w_eff = min(w_eff, int(last_power_w))
            return w_eff

        # Miner drawing 2699W with stale cache "2300W" MUST resolve to 2700W!
        self.assertEqual(resolve_wattage(2699.0, "2300W"), 2700)
        # Miner drawing 2499W with stale cache "2150W" MUST resolve to 2500W!
        self.assertEqual(resolve_wattage(2499.0, "2150W"), 2500)
        # Miner offline or initializing at 0W resolves to 0W
        self.assertEqual(resolve_wattage(0.0, "2500W"), 0)
        self.assertEqual(resolve_wattage(2499.0, "2500W", m_resp=False), 0)

    def test_governance_policy_blocks_preset_mutations_when_presets_disabled(self):
        from app.governance.intervention_policy import (
            ACTION_PRESET_BALANCER,
            InterventionGovernance,
            should_allow_intervention,
        )
        now_ts = 1000.0
        # When presets_enabled is False, should_allow_intervention returns False
        gov = InterventionGovernance(master_enabled=True, presets_enabled=False)
        allowed, reason = should_allow_intervention(ACTION_PRESET_BALANCER, gov, now_ts)
        self.assertFalse(allowed)
        self.assertEqual(reason, "presets_disabled")

        # When master_enabled is False, should_allow_intervention returns False
        gov_master_off = InterventionGovernance(master_enabled=False, presets_enabled=True)
        allowed2, reason2 = should_allow_intervention(ACTION_PRESET_BALANCER, gov_master_off, now_ts)
        self.assertFalse(allowed2)
        self.assertIn("master_interventions_disabled", reason2)


if __name__ == "__main__":
    unittest.main()
