from __future__ import annotations

import unittest

from app.governance.preset_balancer import (
    ACTION_HOLD_STABLE,
    ACTION_LOCKED_MAX,
    ACTION_LOCKED_MIN,
    ACTION_STEP_DOWN_CASCADE,
    ACTION_STEP_DOWN_RESTARTS,
    ACTION_STEP_DOWN_THERMAL,
    ACTION_STEP_UP_OPTIMIZE,
    ACTION_UNKNOWN,
    BalancerConfig,
    DEFAULT_PRESET_LADDER,
    ElevatorSensitivitySummary,
    PresetTier,
    StabilityMetrics,
    analyze_elevator_sensitivity,
    build_balancer_table_text,
    build_elevator_sensitivity_text,
    build_miner_balancer_detail_text,
    compute_effective_hashrate,
    evaluate_balancer_step,
    extract_miner_stability_metrics,
    find_preset_index,
    infer_preset_name_from_power,
    record_elevator_restart_circumstance,
)


class TestPresetBalancer(unittest.TestCase):
    def setUp(self):
        self.cfg = BalancerConfig()

    def test_compute_effective_hashrate(self):
        # 0 restarts at 98 TH/s nominal -> 98.0 TH/s
        eff_0 = compute_effective_hashrate(98.0, restarts_count=0)
        self.assertEqual(eff_0, 98.0)

        # 3 restarts at 98 TH/s nominal with 10m downtime and 2.0 penalty:
        # downtime = 30m / 1440m = 0.02083
        # rate = 98 * (1 - 0.02083) = 95.96 - (3 * 2) = 89.96
        eff_3 = compute_effective_hashrate(98.0, restarts_count=3)
        self.assertAlmostEqual(eff_3, 89.96, places=1)

        # Cost-benefit proof: 93 TH/s with 0 restarts is MORE than 98 TH/s with 3 restarts!
        eff_clean_2500w = compute_effective_hashrate(93.0, restarts_count=0)
        self.assertGreater(eff_clean_2500w, eff_3)

    def test_find_preset_index(self):
        self.assertEqual(find_preset_index("2500W"), 5)
        self.assertEqual(find_preset_index("2700w"), 6)
        self.assertEqual(find_preset_index("nonexistent_preset"), -1)

    def test_unknown_preset(self):
        metrics = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_1",
            current_preset="CUSTOM_9999W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=50.0,
            avg_hashrate_24h_ths=90.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=8.0,
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_UNKNOWN)
        self.assertFalse(dec.requires_write)

    def test_step_down_on_frequent_restarts(self):
        # 2 restarts in 24h at 2700W -> steps down to 2500W
        metrics = StabilityMetrics(
            miner_name="S19JPRO-24",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            restarts_24h=2,
            restarts_72h=3,
            hours_since_last_restart=3.5,
            avg_hashrate_24h_ths=85.0,
            downtime_minutes_24h=25.0,
            thermal_headroom_c=5.0,
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_STEP_DOWN_RESTARTS)
        self.assertEqual(dec.target_preset, "2500W")
        self.assertTrue(dec.requires_write)
        self.assertIn("desescalando a 2500W", dec.reason)

    def test_step_down_at_minimum_preset_locks(self):
        # In minimum tier (1600W) with restarts -> cannot step down further
        metrics = StabilityMetrics(
            miner_name="S19JPRO-24",
            electrical_group="elevator_sensible",
            current_preset="1600W",
            restarts_24h=4,
            restarts_72h=6,
            hours_since_last_restart=1.0,
            avg_hashrate_24h_ths=60.0,
            downtime_minutes_24h=40.0,
            thermal_headroom_c=12.0,
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_LOCKED_MIN)
        self.assertEqual(dec.target_preset, "1600W")
        self.assertFalse(dec.requires_write)

    def test_group_cascade_step_down(self):
        # Miner 23 and Miner 24 are both on elevator_sensible.
        # Both had restarts recently -> cascade step down
        peer_metrics = [
            StabilityMetrics(
                miner_name="S19JPRO-23",
                electrical_group="elevator_sensible",
                current_preset="2500W",
                restarts_24h=1,
                restarts_72h=1,
                hours_since_last_restart=0.2,  # recent restart
                avg_hashrate_24h_ths=90.0,
                downtime_minutes_24h=10.0,
                thermal_headroom_c=6.0,
            ),
            StabilityMetrics(
                miner_name="S19JPRO-24",
                electrical_group="elevator_sensible",
                current_preset="2500W",
                restarts_24h=1,
                restarts_72h=1,
                hours_since_last_restart=0.3,  # recent restart
                avg_hashrate_24h_ths=90.0,
                downtime_minutes_24h=10.0,
                thermal_headroom_c=6.0,
            ),
        ]
        dec = evaluate_balancer_step(
            peer_metrics[1],
            self.cfg,
            group_metrics=peer_metrics,
        )
        self.assertEqual(dec.action, ACTION_STEP_DOWN_CASCADE)
        self.assertEqual(dec.target_preset, "2300W")
        self.assertTrue(dec.requires_write)
        self.assertIn("Caída en cascada", dec.reason)

    def test_step_up_after_soak_stability(self):
        # 80 hours uptime, 0 restarts in 72h, headroom 6.5°C >= 4.0°C -> step up 2300W to 2500W
        metrics = StabilityMetrics(
            miner_name="S19JPRO-25",
            electrical_group="elevator_estable",
            current_preset="2300W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            avg_hashrate_24h_ths=88.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=6.5,
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_STEP_UP_OPTIMIZE)
        self.assertEqual(dec.target_preset, "2500W")
        self.assertTrue(dec.requires_write)
        self.assertIn("subiendo a 2500W", dec.reason)

    def test_step_up_blocked_by_insufficient_thermal_headroom(self):
        # 80 hours uptime but headroom is only 2.5°C (< 4.0°C) -> holds current preset
        metrics = StabilityMetrics(
            miner_name="S19JPRO-25",
            electrical_group="elevator_estable",
            current_preset="2300W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            avg_hashrate_24h_ths=88.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=2.5,  # Too hot!
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_HOLD_STABLE)
        self.assertFalse(dec.requires_write)

    def test_step_up_capped_at_max_preset(self):
        # Already at configured ceiling (e.g. 2700W) -> locked at max
        metrics = StabilityMetrics(
            miner_name="S19JPRO-26",
            electrical_group="elevator_estable",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=100.0,
            avg_hashrate_24h_ths=98.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=7.0,
        )
        dec = evaluate_balancer_step(
            metrics,
            self.cfg,
            max_preset_override="2700W",
        )
        self.assertEqual(dec.action, ACTION_LOCKED_MAX)
        self.assertEqual(dec.target_preset, "2700W")
        self.assertFalse(dec.requires_write)

    def test_step_down_on_thermal_overload(self):
        # Temp >= 84.0°C (headroom <= 1.0°C) forces immediate preset step-down
        metrics = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=10.0,
            avg_hashrate_24h_ths=98.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=0.8,  # 84.2°C
        )
        dec = evaluate_balancer_step(metrics, self.cfg)
        self.assertEqual(dec.action, ACTION_STEP_DOWN_THERMAL)
        self.assertEqual(dec.target_preset, "2500W")
        self.assertTrue(dec.requires_write)
        self.assertIn(">=84.0°C", dec.reason)

    def test_infer_preset_name_from_power(self):
        self.assertEqual(infer_preset_name_from_power(2480), "2500W")
        self.assertEqual(infer_preset_name_from_power(2720), "2700W")
        self.assertEqual(infer_preset_name_from_power(1610), "1600W")
        self.assertEqual(infer_preset_name_from_power(None), "2500W")

    def test_build_balancer_table_text(self):
        m1 = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            restarts_24h=2,
            restarts_72h=3,
            hours_since_last_restart=3.0,
            avg_hashrate_24h_ths=88.0,
            downtime_minutes_24h=20.0,
            thermal_headroom_c=5.0,
        )
        d1 = evaluate_balancer_step(m1, self.cfg)

        m2 = StabilityMetrics(
            miner_name="S19JPRO-25",
            electrical_group="elevator_estable",
            current_preset="2500W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            avg_hashrate_24h_ths=93.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=6.0,
        )
        d2 = evaluate_balancer_step(m2, self.cfg)

        text = build_balancer_table_text([(m1, d1), (m2, d2)], is_enabled=True, is_dry_run=True)
        self.assertIn("Balanceador de Presets", text)
        self.assertIn("Elevadores", text)
        self.assertIn("ELEVATOR_SENSIBLE", text)
        self.assertIn("ELEVATOR_ESTABLE", text)
        self.assertIn("S19JPRO-23: 2700W ➔ 2500W", text)
        self.assertIn("STEP_DOWN_RESTARTS", text)

    def test_build_miner_balancer_detail_text(self):
        m = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_sensible",
            current_preset="2700W",
            restarts_24h=2,
            restarts_72h=3,
            hours_since_last_restart=3.0,
            avg_hashrate_24h_ths=88.0,
            downtime_minutes_24h=20.0,
            thermal_headroom_c=5.0,
        )
        d = evaluate_balancer_step(m, self.cfg)
        card = build_miner_balancer_detail_text(m, d)
        self.assertIn("Balanceador de Potencia", card)
        self.assertIn("S19JPRO-23", card)
        self.assertIn("Elevador: elevator_sensible", card)
        self.assertIn("Reinicios en 24h: 2", card)

    def test_extract_miner_stability_metrics_against_live_db(self):
        import time
        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_sensible"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_sensible"},
            {"name": "S19JPRO-25", "host": "192.168.100.25", "port": 4028, "electrical_group": "elevator_estable"},
            {"name": "S19JPRO-26", "host": "192.168.100.26", "port": 4028, "electrical_group": "elevator_estable"},
        ]
        t0 = time.perf_counter()
        metrics = extract_miner_stability_metrics(
            db_path="data/miner_alerts.db",
            miners=miners,
        )
        query_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(query_ms, 500.0, f"Query took {query_ms:.1f}ms, expected < 500ms")
        self.assertEqual(len(metrics), 4)
        for m in metrics:
            self.assertIn(m.electrical_group, ("elevator_sensible", "elevator_estable"))
            self.assertGreaterEqual(m.thermal_headroom_c, 0.0)

    def test_record_elevator_restart_circumstance_single(self):
        class DummyState:
            governor_last_power_w = 2690.0
            governor_last_temp_c = 81.5
            last_reboot_ts = 0.0
            last_elapsed = 40000
            state = "OK"

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
        ]
        states = {
            "S19JPRO-23|192.168.100.23:4028": DummyState(),
            "S19JPRO-24|192.168.100.24:4028": DummyState(),
        }

        res = record_elevator_restart_circumstance(
            miner_name="S19JPRO-23",
            electrical_group="elevator_1",
            miners=miners,
            states=states,
            now_ts=1700000000.0,
        )
        self.assertEqual(res["electrical_group"], "elevator_1")
        self.assertAlmostEqual(res["group_total_power_w"], 5380.0, places=1)
        self.assertFalse(res["is_elevator_cascade"])
        self.assertIsNone(res["cascade_peer"])

    def test_record_elevator_restart_circumstance_cascade(self):
        class DummyStatePeer:
            governor_last_power_w = 2490.0
            governor_last_temp_c = 82.0
            last_reboot_ts = 1700000000.0 - 120.0  # restarted 2 minutes ago
            last_elapsed = 120
            state = "OK"

        class DummyStateSelf:
            governor_last_power_w = 2690.0
            governor_last_temp_c = 83.0
            last_reboot_ts = 0.0
            last_elapsed = 0
            state = "LOW"

        miners = [
            {"name": "S19JPRO-23", "host": "192.168.100.23", "port": 4028, "electrical_group": "elevator_1"},
            {"name": "S19JPRO-24", "host": "192.168.100.24", "port": 4028, "electrical_group": "elevator_1"},
        ]
        states = {
            "S19JPRO-23|192.168.100.23:4028": DummyStateSelf(),
            "S19JPRO-24|192.168.100.24:4028": DummyStatePeer(),
        }

        res = record_elevator_restart_circumstance(
            miner_name="S19JPRO-23",
            electrical_group="elevator_1",
            miners=miners,
            states=states,
            now_ts=1700000000.0,
            cascade_window_s=1800.0,
        )
        self.assertTrue(res["is_elevator_cascade"])
        self.assertEqual(res["cascade_peer"], "S19JPRO-24")
        self.assertEqual(res["cascade_delta_s"], 120.0)

    def test_analyze_elevator_sensitivity_and_card(self):
        m1 = StabilityMetrics(
            miner_name="S19JPRO-23",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            avg_hashrate_24h_ths=98.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=6.0,
            current_power_w=2695.0,
        )
        m2 = StabilityMetrics(
            miner_name="S19JPRO-24",
            electrical_group="elevator_1",
            current_preset="2700W",
            restarts_24h=0,
            restarts_72h=0,
            hours_since_last_restart=80.0,
            avg_hashrate_24h_ths=98.0,
            downtime_minutes_24h=0.0,
            thermal_headroom_c=5.5,
            current_power_w=2698.0,
        )
        m3 = StabilityMetrics(
            miner_name="S19JPRO-25",
            electrical_group="elevator_2",
            current_preset="2500W",
            restarts_24h=3,
            restarts_72h=4,
            hours_since_last_restart=1.0,
            avg_hashrate_24h_ths=90.0,
            downtime_minutes_24h=30.0,
            thermal_headroom_c=4.0,
            current_power_w=2480.0,
        )

        summaries = analyze_elevator_sensitivity([m1, m2, m3], db_path="nonexistent.db")
        self.assertIn("elevator_1", summaries)
        self.assertIn("elevator_2", summaries)

        s1 = summaries["elevator_1"]
        self.assertEqual(s1.sensitivity_level, "ESTABLE")
        self.assertAlmostEqual(s1.total_load_w, 5393.0, places=1)

        s2 = summaries["elevator_2"]
        self.assertEqual(s2.sensitivity_level, "ALTA_SENSIBILIDAD")
        self.assertIn("Escalar un minero a 2500W", s2.recommendation)

        card = build_elevator_sensitivity_text(summaries)
        self.assertIn("Sensibilidad de Elevadores", card)
        self.assertIn("ELEVATOR_1", card)
        self.assertIn("ELEVATOR_2", card)
        self.assertIn("ALTA_SENSIBILIDAD", card)


if __name__ == "__main__":
    unittest.main()


