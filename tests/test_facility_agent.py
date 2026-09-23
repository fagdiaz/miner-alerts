"""
Unit tests for Facility Governance Agent (FGA) - Spec 079.
"""

import unittest
from app.governance.facility_agent import (
    calculate_thermal_resistance,
    predict_chip_temperature,
    classify_silicon_cohort,
    build_thermal_profile,
    evaluate_asymmetric_allocation,
    explain_miner_state,
    DEFAULT_THERMAL_RESISTANCE,
    STRATEGY_BALANCED,
    STRATEGY_MAX_POWER,
    STRATEGY_EFFICIENCY,
    STRATEGY_COOL_QUIET,
)


class TestFacilityAgentThermalModeling(unittest.TestCase):
    def test_calculate_thermal_resistance_nominal(self):
        # 80°C chip, 25°C inlet, 2500W -> 55 / 2500 = 0.022 °C/W
        r_th = calculate_thermal_resistance(chip_temp_c=80.0, inlet_temp_c=25.0, power_w=2500.0)
        self.assertAlmostEqual(r_th, 0.022, places=4)

    def test_calculate_thermal_resistance_cool_silicon(self):
        # 75°C chip, 25°C inlet, 2700W -> 50 / 2700 = 0.0185 °C/W
        r_th = calculate_thermal_resistance(chip_temp_c=75.0, inlet_temp_c=25.0, power_w=2700.0)
        self.assertAlmostEqual(r_th, 0.01852, places=4)

    def test_calculate_thermal_resistance_fallbacks(self):
        # Missing telemetry
        self.assertEqual(calculate_thermal_resistance(None, 25.0, 2500.0), DEFAULT_THERMAL_RESISTANCE)
        self.assertEqual(calculate_thermal_resistance(80.0, None, 2500.0), DEFAULT_THERMAL_RESISTANCE)
        self.assertEqual(calculate_thermal_resistance(80.0, 25.0, None), DEFAULT_THERMAL_RESISTANCE)
        # Power < 500W (idle/startup)
        self.assertEqual(calculate_thermal_resistance(80.0, 25.0, 200.0), DEFAULT_THERMAL_RESISTANCE)
        # Inverted temp
        self.assertEqual(calculate_thermal_resistance(20.0, 25.0, 2500.0), DEFAULT_THERMAL_RESISTANCE)

    def test_predict_chip_temperature(self):
        # Inlet 25°C, 2700W, R_th = 0.020 -> 25 + 54 = 79.0°C
        pred = predict_chip_temperature(inlet_temp_c=25.0, target_power_w=2700.0, thermal_resistance=0.020)
        self.assertEqual(pred, 79.0)

        # Inlet 30°C, 2700W, R_th = 0.024 -> 30 + 64.8 = 94.8°C (Dangerous!)
        pred_hot = predict_chip_temperature(inlet_temp_c=30.0, target_power_w=2700.0, thermal_resistance=0.024)
        self.assertEqual(pred_hot, 94.8)

    def test_classify_silicon_cohort(self):
        self.assertEqual(classify_silicon_cohort(0.018), "COOL")
        self.assertEqual(classify_silicon_cohort(0.020), "COOL")
        self.assertEqual(classify_silicon_cohort(0.022), "STANDARD")
        self.assertEqual(classify_silicon_cohort(0.024), "STANDARD")
        self.assertEqual(classify_silicon_cohort(0.026), "HOT")

    def test_build_thermal_profile(self):
        prof = build_thermal_profile(
            miner_name="S19JPRO-26",
            chip_temp_c=75.0,
            inlet_temp_c=25.0,
            power_w=2700.0,
            current_preset="2700W",
        )
        self.assertEqual(prof.miner_name, "S19JPRO-26")
        self.assertEqual(prof.cohort, "COOL")
        self.assertFalse(prof.is_overheating)
        self.assertEqual(prof.predicted_temp_2700w, 75.0)
        self.assertGreater(prof.cooling_margin_c, 0.0)


class TestFacilityAgentAsymmetricAllocation(unittest.TestCase):
    def setUp(self):
        # 4-miner fleet matching live production reality
        # Elevator 1: Warm miners (23 & 24)
        # Elevator 2: Cool miners (25 & 26)
        self.miners = [
            {
                "name": "S19JPRO-23",
                "electrical_group": "elevator_1",
                "chip_temp_c": 85.0,
                "inlet_temp_c": 25.0,
                "power_w": 2500.0,
                "preset": "2500W",
            },
            {
                "name": "S19JPRO-24",
                "electrical_group": "elevator_1",
                "chip_temp_c": 82.0,
                "inlet_temp_c": 25.0,
                "power_w": 2500.0,
                "preset": "2500W",
            },
            {
                "name": "S19JPRO-25",
                "electrical_group": "elevator_2",
                "chip_temp_c": 77.0,
                "inlet_temp_c": 25.0,
                "power_w": 2500.0,
                "preset": "2500W",
            },
            {
                "name": "S19JPRO-26",
                "electrical_group": "elevator_2",
                "chip_temp_c": 75.0,
                "inlet_temp_c": 25.0,
                "power_w": 2700.0,
                "preset": "2700W",
            },
        ]

    def test_balanced_strategy_asymmetric_allocation(self):
        decision = evaluate_asymmetric_allocation(self.miners, strategy=STRATEGY_BALANCED)

        # Elevator 1 (Warm): Keep at 2500W
        self.assertEqual(decision.target_allocations["S19JPRO-23"], "2500W")
        self.assertEqual(decision.target_allocations["S19JPRO-24"], "2500W")

        # Elevator 2 (Cool): Authorize 2700W
        self.assertEqual(decision.target_allocations["S19JPRO-26"], "2700W")

        # Total projected power within limits
        self.assertLessEqual(decision.group_projected_power_w["elevator_1"], 5400.0)
        self.assertLessEqual(decision.group_projected_power_w["elevator_2"], 5400.0)
        self.assertLessEqual(decision.total_projected_power_w, 10400.0)

    def test_cool_quiet_strategy(self):
        decision = evaluate_asymmetric_allocation(self.miners, strategy=STRATEGY_COOL_QUIET)
        for name, preset in decision.target_allocations.items():
            self.assertEqual(preset, "2300W")

    def test_group_constraint_prevents_two_2700w_if_limit_is_5000w(self):
        # Constrain group limit to 5000W
        decision = evaluate_asymmetric_allocation(self.miners, max_group_power_w=5000.0, strategy=STRATEGY_MAX_POWER)
        # 2700 + 2700 = 5400 > 5000, so at most one miner in elevator_2 can be 2700W (or both 2500W)
        self.assertLessEqual(decision.group_projected_power_w["elevator_2"], 5000.0)

    def test_explain_miner_state(self):
        prof = build_thermal_profile("S19JPRO-23", 85.0, 25.0, 2500.0, "2500W")
        explanation = explain_miner_state("S19JPRO-23", prof, "2500W", STRATEGY_BALANCED)
        self.assertIn("S19JPRO-23", explanation)
        self.assertIn("Resistencia Térmica", explanation)
        self.assertIn("Margen a Límite Seguro", explanation)


class TestFacilityAgentPersistence(unittest.TestCase):
    def test_upsert_and_get_knowledge(self):
        import tempfile
        from pathlib import Path
        from app.core.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "agent_test.db"
            store = EventStore(db_path, async_check=False)
            self.assertTrue(store.available)

            # Upsert knowledge for S19JPRO-26
            ok = store.upsert_facility_agent_knowledge(
                miner_name="S19JPRO-26",
                thermal_resistance=0.0185,
                best_preset="2700W",
                cohort="COOL",
                last_chip_temp_c=75.0,
                last_inlet_temp_c=25.0,
                last_power_w=2700.0,
                notes="Low thermal resistance, prime candidate for 2700W",
            )
            self.assertTrue(ok)

            # Retrieve knowledge
            rows = store.get_facility_agent_knowledge("S19JPRO-26")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["miner_name"], "S19JPRO-26")
            self.assertAlmostEqual(rows[0]["thermal_resistance"], 0.0185, places=4)
            self.assertEqual(rows[0]["cohort"], "COOL")
            self.assertEqual(rows[0]["best_preset"], "2700W")
            store.close()


if __name__ == "__main__":
    unittest.main()
