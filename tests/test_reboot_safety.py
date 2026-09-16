import inspect
import json
import math
import unittest
from pathlib import Path

import app.miner_monitor as monitor
from app.core.reboot_safety import (
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
        """Verify the gate order hierarchy and timer resets via ActuatorHook."""
        from app.core.engine import ActuatorHook
        from app.core.reboot_safety import RebootInterlockDecision, INTERLOCK_FIRMWARE_TRANSITION

        st = monitor.MinerState(state=monitor.STATE_LOW, low_since_ts=1000.0)

        # 1. Startup guard precede sostenido
        res_startup = ActuatorHook.evaluate_auto_reboot_policy(
            state=st, miner={"name": "M1"}, new_state=monitor.STATE_LOW, responded=True,
            rate_ths=20.0, threshold_ths=60.0, active_boards=3, now_ts=500.0,
            process_start_ts=0.0, startup_guard_seconds=600, low_sustained_seconds=900,
        )
        self.assertEqual("startup_guard", res_startup["reason"])

        # 2. Sostenido precede interlocks
        res_sustained = ActuatorHook.evaluate_auto_reboot_policy(
            state=st, miner={"name": "M1"}, new_state=monitor.STATE_LOW, responded=True,
            rate_ths=20.0, threshold_ths=60.0, active_boards=3, now_ts=1200.0,
            process_start_ts=0.0, startup_guard_seconds=600, low_sustained_seconds=900,
        )
        self.assertEqual("not_sustained", res_sustained["reason"])

        # 3. Interlocks bloquea y transición de firmware resetea low_since_ts a now_ts
        dec = RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_FIRMWARE_TRANSITION,
            chains_transitioning_count=1,
        )
        res_interlock = ActuatorHook.evaluate_auto_reboot_policy(
            state=st, miner={"name": "M1"}, new_state=monitor.STATE_LOW, responded=True,
            rate_ths=20.0, threshold_ths=60.0, active_boards=3, now_ts=2500.0,
            process_start_ts=0.0, startup_guard_seconds=600, low_sustained_seconds=900,
            interlock_decision=dec,
        )
        self.assertEqual(INTERLOCK_FIRMWARE_TRANSITION, res_interlock["reason"])
        self.assertEqual(2500.0, st.low_since_ts)

        # 4. Cooldown delta bloquea antes de ejecución
        st.low_since_ts = 1000.0
        st.last_auto_reboot_ts = 2400.0  # 100s atrás < 1800s cooldown
        res_cooldown = ActuatorHook.evaluate_auto_reboot_policy(
            state=st, miner={"name": "M1"}, new_state=monitor.STATE_LOW, responded=True,
            rate_ths=20.0, threshold_ths=60.0, active_boards=3, now_ts=2500.0,
            process_start_ts=0.0, startup_guard_seconds=600, low_sustained_seconds=900,
            reboot_cooldown_seconds=1800,
        )
        self.assertEqual("cooldown", res_cooldown["reason"])

        # 5. Worker de telegram polling no ejecuta guardas de transición de firmware
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
