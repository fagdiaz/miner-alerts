import unittest

from app.vnish_telemetry import normalize_vnish_stats


class VnishTelemetryTests(unittest.TestCase):
    def test_extracts_real_shaped_fields_from_second_stats_entry(self) -> None:
        response = {
            "STATS": [
                {"STATUS": "S"},
                {
                    "chain_vol1": 12825,
                    "chain_vol2": "12825",
                    "chain_vol3": 12825.0,
                    "chain_consumption1": 902,
                    "chain_consumption2": 899,
                    "chain_consumption3": 897,
                    "freq_avg1": 517.5952,
                    "freq_avg2": 515.8333,
                    "freq_avg3": 514.5,
                    "chain_hw1": 22,
                    "chain_hw2": 0,
                    "chain_hw3": 0,
                    "fan_pwm": 100,
                    "fan1": 5790,
                    "fan2": 6000,
                    "temp_chip1": 78,
                    "temp_pcb1": 63,
                },
            ]
        }

        telemetry = normalize_vnish_stats(response, expected_boards=3)

        self.assertEqual(78.0, telemetry.max_temp_c)
        self.assertEqual(12825.0, telemetry.chain_voltage_mv_avg)
        self.assertEqual(2698.0, telemetry.chain_power_w_total)
        self.assertEqual(515.976, telemetry.frequency_mhz_avg)
        self.assertEqual(22, telemetry.hw_errors_total)
        self.assertEqual(6000, telemetry.fan_rpm_max)
        self.assertEqual(100.0, telemetry.fan_pwm_percent)
        self.assertEqual(("hw_errors_present",), telemetry.diagnostic_flags)

    def test_missing_and_malformed_values_remain_unknown(self) -> None:
        telemetry = normalize_vnish_stats(
            {"STATS": [{"chain_vol1": "bad", "temp1": -1, "fan1": None}]},
            expected_boards=3,
        )

        self.assertIsNone(telemetry.max_temp_c)
        self.assertIsNone(telemetry.chain_voltage_mv_avg)
        self.assertIsNone(telemetry.hw_errors_total)
        self.assertIn("telemetry_incomplete", telemetry.diagnostic_flags)
        self.assertIn("chain_signal_below_expected", telemetry.diagnostic_flags)

    def test_flags_high_temperature_missing_chain_and_missing_fan(self) -> None:
        telemetry = normalize_vnish_stats(
            {
                "STATS": {
                    "chain_vol1": 12500,
                    "chain_consumption1": 850,
                    "freq_avg1": 490,
                    "chain_hw1": 0,
                    "temp_chip1": 90,
                }
            },
            expected_boards=3,
        )

        self.assertEqual(
            ("chain_signal_below_expected", "high_temperature", "fan_signal_missing"),
            telemetry.diagnostic_flags,
        )

    def test_deduplicates_nested_chain_keys_by_index(self) -> None:
        telemetry = normalize_vnish_stats(
            {
                "STATS": [
                    {"chain_vol1": 12000},
                    {"nested": {"chain_vol1": 13000, "chain_vol2": 14000}},
                ]
            }
        )

        self.assertEqual(13500.0, telemetry.chain_voltage_mv_avg)


if __name__ == "__main__":
    unittest.main()
