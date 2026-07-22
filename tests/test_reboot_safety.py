import inspect
import json
import math
import unittest
from pathlib import Path

import app.miner_monitor as monitor
from app.reboot_safety import (
    INTERLOCK_FIRMWARE_TRANSITION,
    INTERLOCK_FLEET_INCIDENT,
    INTERLOCK_HIGH_TEMPERATURE,
    evaluate_auto_reboot_interlocks,
)


class RebootSafetyInterlockTests(unittest.TestCase):
    def test_current_firmware_transition_blocks_auto_reboot(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=78.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
            firmware_transition_guard_enabled=True,
            chains_transitioning_count=1,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(INTERLOCK_FIRMWARE_TRANSITION, decision.reason)
        self.assertEqual(1, decision.chains_transitioning_count)

    def test_transition_unknown_zero_or_disabled_does_not_block(self) -> None:
        for enabled, count in (
            (True, None),
            (True, 0),
            (True, "bad"),
            (False, 2),
        ):
            with self.subTest(enabled=enabled, count=count):
                decision = evaluate_auto_reboot_interlocks(
                    current_miner_key="m23",
                    current_signal="eligible",
                    previous_signals={},
                    previous_signals_observed_ts=None,
                    evaluated_ts=1_000.0,
                    fleet_snapshot_max_age_seconds=60.0,
                    max_temp_c=78.0,
                    thermal_guard_enabled=True,
                    thermal_limit_c=85.0,
                    fleet_guard_enabled=False,
                    fleet_min_affected=2,
                    firmware_transition_guard_enabled=enabled,
                    chains_transitioning_count=count,
                )
                self.assertTrue(decision.allowed)

    def test_thermal_guard_precedes_firmware_transition(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=90.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
            firmware_transition_guard_enabled=True,
            chains_transitioning_count=1,
        )

        self.assertEqual(INTERLOCK_HIGH_TEMPERATURE, decision.reason)

    def test_single_low_candidate_remains_allowed(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m23": "eligible", "m24": "not_low"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=78.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )

        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason)
        self.assertEqual(("m23",), decision.affected_miners)

    def test_shared_low_and_invalid_signal_block_as_fleet_incident(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={
                "m23": "eligible",
                "m24": "invalid_signal",
                "m25": "not_low",
            },
            previous_signals_observed_ts=990.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=78.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(INTERLOCK_FLEET_INCIDENT, decision.reason)
        self.assertEqual(("m23", "m24"), decision.affected_miners)

    def test_missing_completed_fleet_observation_does_not_invent_peers(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=None,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(("m23",), decision.affected_miners)

    def test_fleet_minimum_is_never_less_than_two(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "not_low"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=None,
            thermal_guard_enabled=False,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=1,
        )

        self.assertTrue(decision.allowed)

    def test_temperature_at_limit_blocks_before_fleet_reason(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=85.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(INTERLOCK_HIGH_TEMPERATURE, decision.reason)
        self.assertEqual(85.0, decision.max_temp_c)

    def test_unknown_or_non_finite_temperature_does_not_block(self) -> None:
        for value in (None, "bad", math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                decision = evaluate_auto_reboot_interlocks(
                    current_miner_key="m23",
                    current_signal="eligible",
                    previous_signals={},
                    previous_signals_observed_ts=None,
                    evaluated_ts=1_000.0,
                    fleet_snapshot_max_age_seconds=60.0,
                    max_temp_c=value,
                    thermal_guard_enabled=True,
                    thermal_limit_c=85.0,
                    fleet_guard_enabled=False,
                    fleet_min_affected=2,
                )
                self.assertTrue(decision.allowed)

    def test_disabled_guards_preserve_existing_action_eligibility(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=95.0,
            thermal_guard_enabled=False,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
        )

        self.assertTrue(decision.allowed)

    def test_stale_fleet_snapshot_is_ignored(self) -> None:
        decision = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=900.0,
            evaluated_ts=1_000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=78.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(("m23",), decision.affected_miners)
        self.assertEqual(100.0, decision.fleet_snapshot_age_seconds)

    def test_runtime_wiring_keeps_gate_order_and_publishes_completed_tick(self) -> None:
        source = inspect.getsource(monitor.main)
        startup = source.index("elif startup_guard_active")
        sustained = source.index("elif (now_ts - state.low_since_ts) < low_sustained_seconds")
        interlock = source.index("elif not interlock_decision.allowed")
        cooldown = source.index("last_reboot_ts = None")
        hashcore = source.index("run_hashcore_cli(hashcore_cfg, miner, \"reboot\"")

        self.assertLess(startup, sustained)
        self.assertLess(sustained, interlock)
        self.assertLess(interlock, cooldown)
        self.assertLess(cooldown, hashcore)
        self.assertIn(
            "chains_transitioning_count=quality_telemetry.chains_transitioning_count",
            source,
        )
        interlock_branch = source.index("elif not interlock_decision.allowed")
        transition_reset = source.index("state.low_since_ts = now_ts", interlock_branch)
        thermal_branch = source.index('interlock_reason == "high_temperature"', interlock_branch)
        self.assertLess(transition_reset, thermal_branch)
        self.assertLess(transition_reset, cooldown)
        self.assertIn("current_tick_signals[state_key] = auto_reboot_signal", source)
        self.assertIn("previous_tick_signals = current_tick_signals.copy()", source)
        self.assertNotIn(
            "firmware_transition_guard",
            inspect.getsource(monitor.telegram_polling_worker),
        )

    def test_production_example_enables_conservative_defaults(self) -> None:
        config = json.loads(
            Path("app/config.example.json").read_text(encoding="utf-8")
        )

        self.assertIs(True, config["auto_reboot_thermal_guard_enabled"])
        self.assertEqual(85.0, config["auto_reboot_max_temp_c"])
        self.assertIs(True, config["auto_reboot_fleet_guard_enabled"])
        self.assertEqual(2, config["auto_reboot_fleet_guard_min_affected"])
        self.assertIs(True, config["auto_reboot_firmware_transition_guard_enabled"])
        self.assertEqual(30, config["state_change_coalesce_seconds"])
        self.assertEqual(
            [300, 600, 900, 1800, 3600, 7200],
            config["persistent_outage_schedule_seconds"],
        )


if __name__ == "__main__":
    unittest.main()
