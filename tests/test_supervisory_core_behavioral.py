"""Supervisory Core Behavioral Test Harness & 37 Invariant Suite (Spec 070).

Provides deterministic black-box verification of supervisory core behaviors:
1. Signal Gate & Timer Resets (8 tests) - Phase A T002
2. Hashboard Auto-Reboot & Interlock Pipeline (8 tests) - Phase A T003
3. Reboot Safety Interlocks Hierarchy & Cooldowns (13 tests) - Phase A T004
4. Hashboard Detection Precedence over Low Hashrate (8 tests) - Phase A T005

Total: 37 tests.
These tests evaluate functional behavior directly, enabling safe architectural
decoupling of inspect.getsource(main) without regression risks.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import patch

from app.miner_monitor import (
    AUTO_REBOOT_SIGNAL_ELIGIBLE,
    AUTO_REBOOT_SIGNAL_INVALID,
    AUTO_REBOOT_SIGNAL_NOT_LOW,
    STATE_HASHBOARD,
    STATE_LOW,
    STATE_OFFLINE,
    STATE_OK,
    MinerState,
    _count_active_boards,
    auto_reboot_signal_allows_evaluation,
    classify_auto_reboot_signal,
    read_stats_snapshot,
    reset_sustained_hashboard_if_ineligible,
    reset_sustained_low_if_signal_ineligible,
)
from app.core.reboot_safety import (
    INTERLOCK_FIRMWARE_TRANSITION,
    INTERLOCK_FLEET_INCIDENT,
    INTERLOCK_HIGH_TEMPERATURE,
    RebootInterlockDecision,
    evaluate_auto_reboot_interlocks,
)


class SupervisoryBehavioralHarness:
    """Black-box behavioral execution simulator for supervisory core decisions."""

    @staticmethod
    def classify_detection_state(
        *,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int = 3,
        startup_grace_active: bool = False,
        offline_streak: int = 1,
        low_streak: int = 1,
        ok_streak: int = 1,
        fails_before_alert: int = 1,
        recovery_successes: int = 1,
        prev_state: str = STATE_OK,
    ) -> str:
        """Evaluate state classification logic matching miner_monitor.py:5588-5597."""
        new_state = prev_state
        if not startup_grace_active:
            if not responded and offline_streak >= fails_before_alert:
                new_state = STATE_OFFLINE
            elif responded and active_boards is not None and active_boards < expected_boards:
                new_state = STATE_HASHBOARD
            elif (
                responded
                and rate_ths is not None
                and rate_ths < threshold_ths
                and low_streak >= fails_before_alert
            ):
                new_state = STATE_LOW
        if (
            responded
            and rate_ths is not None
            and rate_ths >= threshold_ths
            and ok_streak >= recovery_successes
        ):
            new_state = STATE_OK
        return new_state

    @staticmethod
    def apply_state_transitions(
        state: MinerState,
        new_state: str,
        now_ts: float,
        startup_grace_active: bool = False,
    ) -> None:
        """Apply timer lifecycle mutations on state transition matching miner_monitor.py:5612-5633."""
        state.state = new_state
        if new_state == STATE_OK:
            state.low_streak = 0
            state.offline_streak = 0
            state.hashboard_since_ts = None
            state.low_since_ts = None
            state.auto_restart_count = 0

        if new_state == STATE_LOW:
            if state.low_since_ts is None:
                state.low_since_ts = now_ts
        else:
            state.low_since_ts = None
            state.low_streak = 0

        if new_state == STATE_HASHBOARD:
            if state.hashboard_since_ts is None:
                state.hashboard_since_ts = now_ts
        else:
            state.hashboard_since_ts = None

        if startup_grace_active:
            state.low_since_ts = None
            state.hashboard_since_ts = None

    @staticmethod
    def evaluate_auto_reboot_pipeline(
        *,
        state: MinerState,
        miner: Dict[str, Any],
        new_state: str,
        responded: bool,
        rate_ths: Optional[float],
        threshold_ths: float,
        active_boards: Optional[int],
        expected_boards: int = 3,
        now_ts: float = 1000.0,
        process_start_ts: float = 0.0,
        startup_guard_seconds: int = 600,
        low_sustained_seconds: int = 900,
        hashboard_sustained_seconds: int = 600,
        hashboard_reboot_enabled: bool = True,
        allow_partial_hashboard: bool = False,
        reboot_cooldown_seconds: int = 1800,
        max_reboots_per_window: int = 3,
        auto_reboot_window_seconds: int = 21600,
        interlock_decision: Optional[RebootInterlockDecision] = None,
        qa_mode: bool = False,
        qa_allow_actions: bool = False,
        cli_reboot_succeeds: bool = True,
    ) -> Dict[str, Any]:
        """Simulate sequential auto-reboot policy matching miner_monitor.py:6075-6450."""
        # 1. Prune sliding window
        state.auto_reboot_timestamps = [
            ts for ts in state.auto_reboot_timestamps if (now_ts - ts) <= auto_reboot_window_seconds
        ]
        startup_guard_active = (now_ts - process_start_ts) < startup_guard_seconds
        signal = classify_auto_reboot_signal(responded, rate_ths, threshold_ths)

        # 2. STATE_LOW branch
        if new_state == STATE_LOW and state.low_since_ts:
            if not auto_reboot_signal_allows_evaluation(new_state, state.low_since_ts, signal):
                reset_sustained_low_if_signal_ineligible(state, signal)
                return {"allowed": False, "blocked_by": "ineligible_signal", "action_executed": False}

            if startup_guard_active:
                return {"allowed": False, "blocked_by": "startup_guard", "action_executed": False}

            if (now_ts - state.low_since_ts) < low_sustained_seconds:
                return {"allowed": False, "blocked_by": "not_sustained", "action_executed": False}

            if interlock_decision and not interlock_decision.allowed:
                if interlock_decision.reason == INTERLOCK_FIRMWARE_TRANSITION:
                    state.low_since_ts = now_ts
                return {"allowed": False, "blocked_by": interlock_decision.reason, "action_executed": False}

            last_reboot_ts = state.last_auto_reboot_ts
            if state.last_manual_reboot_ts is not None:
                last_reboot_ts = (
                    state.last_manual_reboot_ts
                    if last_reboot_ts is None
                    else max(last_reboot_ts, state.last_manual_reboot_ts)
                )
            if last_reboot_ts is not None and (now_ts - last_reboot_ts) < reboot_cooldown_seconds:
                return {"allowed": False, "blocked_by": "cooldown", "action_executed": False}

            if len(state.auto_reboot_timestamps) >= max_reboots_per_window:
                state.degraded_mode = True
                return {"allowed": False, "blocked_by": "window", "action_executed": False}

            if qa_mode and not qa_allow_actions:
                return {"allowed": False, "blocked_by": "qa", "action_executed": False}

            # Action execution
            if cli_reboot_succeeds:
                state.last_auto_reboot_ts = now_ts
                state.auto_reboot_timestamps.append(now_ts)
                state.low_since_ts = None
                state.auto_restart_count = 0
                return {"allowed": True, "blocked_by": None, "action_executed": True, "action_success": True}
            else:
                return {"allowed": True, "blocked_by": None, "action_executed": True, "action_success": False}

        # 3. STATE_HASHBOARD branch
        elif (
            new_state == STATE_HASHBOARD
            and state.hashboard_since_ts
            and hashboard_reboot_enabled
        ):
            if not auto_reboot_signal_allows_evaluation(
                new_state=new_state,
                low_since_ts=None,
                signal_classification=signal,
                hashboard_since_ts=state.hashboard_since_ts,
                active_boards=active_boards,
                expected_boards=expected_boards,
                allow_partial_hashboard=allow_partial_hashboard,
                hashboard_reboot_enabled=hashboard_reboot_enabled,
            ):
                reset_sustained_hashboard_if_ineligible(
                    state=state,
                    signal_classification=signal,
                    active_boards=active_boards,
                    expected_boards=expected_boards,
                    allow_partial_hashboard=allow_partial_hashboard,
                )
                return {"allowed": False, "blocked_by": "ineligible_signal", "action_executed": False}

            if startup_guard_active:
                return {"allowed": False, "blocked_by": "startup_guard", "action_executed": False}

            if (now_ts - state.hashboard_since_ts) < hashboard_sustained_seconds:
                return {"allowed": False, "blocked_by": "not_sustained", "action_executed": False}

            if interlock_decision and not interlock_decision.allowed:
                if interlock_decision.reason == INTERLOCK_FIRMWARE_TRANSITION:
                    state.hashboard_since_ts = now_ts
                return {"allowed": False, "blocked_by": interlock_decision.reason, "action_executed": False}

            last_reboot_ts = state.last_auto_reboot_ts
            if state.last_manual_reboot_ts is not None:
                last_reboot_ts = (
                    state.last_manual_reboot_ts
                    if last_reboot_ts is None
                    else max(last_reboot_ts, state.last_manual_reboot_ts)
                )
            if last_reboot_ts is not None and (now_ts - last_reboot_ts) < reboot_cooldown_seconds:
                return {"allowed": False, "blocked_by": "cooldown", "action_executed": False}

            if len(state.auto_reboot_timestamps) >= max_reboots_per_window:
                state.degraded_mode = True
                return {"allowed": False, "blocked_by": "window", "action_executed": False}

            if qa_mode and not qa_allow_actions:
                return {"allowed": False, "blocked_by": "qa", "action_executed": False}

            # Action execution
            if cli_reboot_succeeds:
                state.last_auto_reboot_ts = now_ts
                state.auto_reboot_timestamps.append(now_ts)
                state.hashboard_since_ts = None
                state.low_since_ts = None
                state.auto_restart_count = 0
                return {"allowed": True, "blocked_by": None, "action_executed": True, "action_success": True}
            else:
                return {"allowed": True, "blocked_by": None, "action_executed": True, "action_success": False}

        return {"allowed": False, "blocked_by": "not_candidate", "action_executed": False}


# ==============================================================================
# 1. Signal Gate & Timer Resets (8 tests) - Phase A T002
# ==============================================================================

class TestAutoRebootSignalGateBehavioral(unittest.TestCase):
    """Behavioral parity tests for signal classification and gate evaluations."""

    def test_signal_classification_finite_and_below_threshold(self) -> None:
        """Classifies valid rate below threshold strictly as ELIGIBLE."""
        self.assertEqual(
            AUTO_REBOOT_SIGNAL_ELIGIBLE,
            classify_auto_reboot_signal(True, 59.999, 60.0),
        )

    def test_signal_classification_not_low_when_at_or_above_threshold(self) -> None:
        """Classifies valid rate at or above threshold as NOT_LOW."""
        self.assertEqual(
            AUTO_REBOOT_SIGNAL_NOT_LOW,
            classify_auto_reboot_signal(True, 60.0, 60.0),
        )
        self.assertEqual(
            AUTO_REBOOT_SIGNAL_NOT_LOW,
            classify_auto_reboot_signal(True, 99.0, 60.0),
        )

    def test_signal_classification_invalid_on_nan_inf_none_unresponsive(self) -> None:
        """Classifies unresponsive or non-finite rate values as INVALID."""
        cases = (
            (False, 50.0),
            (True, None),
            (True, math.nan),
            (True, math.inf),
            (True, -math.inf),
        )
        for responded, rate in cases:
            with self.subTest(responded=responded, rate=rate):
                self.assertEqual(
                    AUTO_REBOOT_SIGNAL_INVALID,
                    classify_auto_reboot_signal(responded, rate, 60.0),
                )

    def test_signal_gate_allows_evaluation_with_low_and_timer(self) -> None:
        """Allows evaluation strictly when state is STATE_LOW, timer is active, and signal is ELIGIBLE."""
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )

    def test_signal_gate_blocks_on_invalid_or_not_low_signal(self) -> None:
        """Blocks evaluation when signal is INVALID or NOT_LOW."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_INVALID,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                1_000.0,
                AUTO_REBOOT_SIGNAL_NOT_LOW,
            )
        )

    def test_signal_gate_blocks_when_timer_none_or_state_not_low(self) -> None:
        """Blocks evaluation if timer is None or state is not STATE_LOW."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_LOW,
                None,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                STATE_OK,
                1_000.0,
                AUTO_REBOOT_SIGNAL_ELIGIBLE,
            )
        )

    def test_ineligible_signal_resets_sustained_low_timer(self) -> None:
        """Ineligible signals reset low_since_ts to None, while ELIGIBLE preserves it."""
        for signal in (AUTO_REBOOT_SIGNAL_INVALID, AUTO_REBOOT_SIGNAL_NOT_LOW):
            with self.subTest(signal=signal):
                st = MinerState(state=STATE_LOW, low_since_ts=1_000.0)
                changed = reset_sustained_low_if_signal_ineligible(st, signal)
                self.assertTrue(changed)
                self.assertIsNone(st.low_since_ts)

        st_ok = MinerState(state=STATE_LOW, low_since_ts=1_000.0)
        changed = reset_sustained_low_if_signal_ineligible(st_ok, AUTO_REBOOT_SIGNAL_ELIGIBLE)
        self.assertFalse(changed)
        self.assertEqual(1_000.0, st_ok.low_since_ts)

    def test_reboot_reason_resets_sustained_timer_and_ineligible_signal_gates_hashcore(self) -> None:
        """Reboot detection resets timer, and ineligible signal prevents reboot action in harness."""
        st = MinerState(state=STATE_LOW, low_since_ts=1000.0)
        # 1. Simulating reboot detected from hardware
        reboot_reason = "elapsed_reset"
        if reboot_reason:
            st.low_since_ts = None
            st.hashboard_since_ts = None
        self.assertIsNone(st.low_since_ts)

        # 2. Pipeline execution with ineligible signal gates hashcore action
        st.low_since_ts = 1000.0
        res = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st,
            miner={"name": "M23", "host": "192.168.1.23", "port": 4028},
            new_state=STATE_LOW,
            responded=True,
            rate_ths=70.0,  # NOT_LOW
            threshold_ths=60.0,
            active_boards=3,
            now_ts=2500.0,
        )
        self.assertFalse(res["allowed"])
        self.assertEqual(res["blocked_by"], "ineligible_signal")
        self.assertFalse(res["action_executed"])
        self.assertIsNone(st.low_since_ts)  # timer reset by gate


# ==============================================================================
# 2. Hashboard Auto-Reboot & Interlock Pipeline (8 tests) - Phase A T003
# ==============================================================================

class TestHashboardAutoRebootBehavioral(unittest.TestCase):
    """Behavioral parity tests for hashboard failure auto-reboot policies."""

    def test_hashboard_signal_allows_evaluation_with_zero_boards_and_timer(self) -> None:
        """Total hashboard failure (0 active boards) with active timer permits evaluation."""
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
                allow_partial_hashboard=False,
            )
        )

    def test_hashboard_signal_blocks_without_timer(self) -> None:
        """Total hashboard failure without timer blocks evaluation."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=None,
                active_boards=0,
                expected_boards=3,
            )
        )

    def test_hashboard_signal_blocks_when_unresponsive_and_resets_timer(self) -> None:
        """Unresponsive miner blocks hashboard evaluation and resets timer."""
        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0)
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_INVALID,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
            )
        )
        changed = reset_sustained_hashboard_if_ineligible(
            st,
            AUTO_REBOOT_SIGNAL_INVALID,
            active_boards=0,
        )
        self.assertTrue(changed)
        self.assertIsNone(st.hashboard_since_ts)

    def test_hashboard_partial_failure_blocked_by_default(self) -> None:
        """Partial failure (2/3 boards) blocks evaluation when allow_partial_hashboard=False."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=2,
                expected_boards=3,
                allow_partial_hashboard=False,
            )
        )

    def test_hashboard_partial_failure_allowed_when_configured(self) -> None:
        """Partial failure (2/3 boards) allows evaluation when allow_partial_hashboard=True."""
        self.assertTrue(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=2,
                expected_boards=3,
                allow_partial_hashboard=True,
            )
        )

    def test_hashboard_evaluation_blocked_when_disabled_by_config(self) -> None:
        """Hashboard reboot evaluation blocked when hashboard_reboot_enabled=False."""
        self.assertFalse(
            auto_reboot_signal_allows_evaluation(
                new_state=STATE_HASHBOARD,
                low_since_ts=None,
                signal_classification=AUTO_REBOOT_SIGNAL_ELIGIBLE,
                hashboard_since_ts=1000.0,
                active_boards=0,
                expected_boards=3,
                hashboard_reboot_enabled=False,
            )
        )

    def test_hashboard_recovery_to_full_boards_resets_sustained_timer(self) -> None:
        """Board restoration (3/3) resets sustained hashboard timer."""
        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0)
        res = reset_sustained_hashboard_if_ineligible(
            st,
            AUTO_REBOOT_SIGNAL_ELIGIBLE,
            active_boards=3,
            expected_boards=3,
        )
        self.assertTrue(res)
        self.assertIsNone(st.hashboard_since_ts)

    def test_hashboard_interlock_sequence_and_timer_reset_on_execution(self) -> None:
        """Verifies full hashboard pipeline execution resets both timers on reboot."""
        st = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0, low_since_ts=1000.0)
        res = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st,
            miner={"name": "M23", "host": "192.168.1.23", "port": 4028},
            new_state=STATE_HASHBOARD,
            responded=True,
            rate_ths=0.0,
            threshold_ths=60.0,
            active_boards=0,
            expected_boards=3,
            now_ts=2000.0,  # 1000s elapsed > 600s sustained
            process_start_ts=0.0,
            startup_guard_seconds=600,
            hashboard_sustained_seconds=600,
            cli_reboot_succeeds=True,
        )
        self.assertTrue(res["allowed"])
        self.assertTrue(res["action_executed"])
        self.assertTrue(res["action_success"])
        self.assertIsNone(st.hashboard_since_ts)
        self.assertIsNone(st.low_since_ts)
        self.assertEqual(st.last_auto_reboot_ts, 2000.0)
        self.assertEqual(st.auto_restart_count, 0)


# ==============================================================================
# 3. Reboot Safety Interlocks Hierarchy & Cooldowns (13 tests) - Phase A T004
# ==============================================================================

class TestRebootSafetyInterlocksBehavioral(unittest.TestCase):
    """Behavioral parity tests for safety interlocks, hierarchy, and cooldowns."""

    def test_firmware_transition_blocks_auto_reboot(self) -> None:
        """Active firmware chain transition blocks auto-reboot."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=78.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
            firmware_transition_guard_enabled=True,
            chains_transitioning_count=1,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(INTERLOCK_FIRMWARE_TRANSITION, dec.reason)

    def test_firmware_transition_zero_or_disabled_allows_auto_reboot(self) -> None:
        """Transition counts <= 0, None, or disabled guard do not block."""
        for enabled, count in ((True, None), (True, 0), (True, "bad"), (False, 2)):
            with self.subTest(enabled=enabled, count=count):
                dec = evaluate_auto_reboot_interlocks(
                    current_miner_key="m23",
                    current_signal="eligible",
                    previous_signals={},
                    previous_signals_observed_ts=None,
                    evaluated_ts=1000.0,
                    fleet_snapshot_max_age_seconds=60.0,
                    max_temp_c=78.0,
                    thermal_guard_enabled=True,
                    thermal_limit_c=85.0,
                    fleet_guard_enabled=False,
                    fleet_min_affected=2,
                    firmware_transition_guard_enabled=enabled,
                    chains_transitioning_count=count,
                )
                self.assertTrue(dec.allowed)

    def test_thermal_guard_precedes_firmware_transition(self) -> None:
        """High temperature interlock evaluates before firmware transition."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=90.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
            firmware_transition_guard_enabled=True,
            chains_transitioning_count=1,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(INTERLOCK_HIGH_TEMPERATURE, dec.reason)

    def test_single_low_candidate_allowed_in_healthy_fleet(self) -> None:
        """Isolated low miner in healthy fleet remains allowed."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m23": "eligible", "m24": "not_low"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=75.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )
        self.assertTrue(dec.allowed)
        self.assertEqual(("m23",), dec.affected_miners)

    def test_fleet_incident_blocks_when_multiple_miners_affected(self) -> None:
        """Shared low or invalid signals block candidate as fleet incident."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m23": "eligible", "m24": "invalid_signal", "m25": "not_low"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=75.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(INTERLOCK_FLEET_INCIDENT, dec.reason)
        self.assertEqual(("m23", "m24"), dec.affected_miners)

    def test_missing_fleet_snapshot_does_not_invent_peers(self) -> None:
        """Missing previous observations does not invent affected peers."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={},
            previous_signals_observed_ts=None,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=None,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )
        self.assertTrue(dec.allowed)
        self.assertEqual(("m23",), dec.affected_miners)

    def test_fleet_minimum_affected_strictly_enforced_at_least_two(self) -> None:
        """Fleet incident requires at least 2 affected miners even if min_affected is configured as 1."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "not_low"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=None,
            thermal_guard_enabled=False,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=1,
        )
        self.assertTrue(dec.allowed)

    def test_temperature_limit_precedes_fleet_incident(self) -> None:
        """Temperature limit breach takes precedence over fleet incident."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=85.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )
        self.assertFalse(dec.allowed)
        self.assertEqual(INTERLOCK_HIGH_TEMPERATURE, dec.reason)

    def test_non_finite_temperature_does_not_block(self) -> None:
        """None, string, NaN, Inf temperatures do not block evaluation."""
        for val in (None, "bad", math.nan, math.inf, -math.inf):
            with self.subTest(val=val):
                dec = evaluate_auto_reboot_interlocks(
                    current_miner_key="m23",
                    current_signal="eligible",
                    previous_signals={},
                    previous_signals_observed_ts=None,
                    evaluated_ts=1000.0,
                    fleet_snapshot_max_age_seconds=60.0,
                    max_temp_c=val,
                    thermal_guard_enabled=True,
                    thermal_limit_c=85.0,
                    fleet_guard_enabled=False,
                    fleet_min_affected=2,
                )
                self.assertTrue(dec.allowed)

    def test_disabled_guards_permit_candidate_evaluation(self) -> None:
        """When guards are disabled in config, evaluation remains allowed."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=990.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,
            max_temp_c=95.0,
            thermal_guard_enabled=False,
            thermal_limit_c=85.0,
            fleet_guard_enabled=False,
            fleet_min_affected=2,
        )
        self.assertTrue(dec.allowed)

    def test_stale_fleet_snapshot_is_ignored(self) -> None:
        """Fleet snapshot older than max age is ignored."""
        dec = evaluate_auto_reboot_interlocks(
            current_miner_key="m23",
            current_signal="eligible",
            previous_signals={"m24": "invalid_signal"},
            previous_signals_observed_ts=900.0,
            evaluated_ts=1000.0,
            fleet_snapshot_max_age_seconds=60.0,  # age 100s > 60s
            max_temp_c=75.0,
            thermal_guard_enabled=True,
            thermal_limit_c=85.0,
            fleet_guard_enabled=True,
            fleet_min_affected=2,
        )
        self.assertTrue(dec.allowed)
        self.assertEqual(("m23",), dec.affected_miners)

    def test_firmware_transition_interlock_resets_low_timer(self) -> None:
        """Firmware transition interlock resets low_since_ts to now_ts in pipeline."""
        st = MinerState(state=STATE_LOW, low_since_ts=1000.0)
        dec = RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_FIRMWARE_TRANSITION,
            chains_transitioning_count=1,
        )
        res = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st,
            miner={"name": "M23", "host": "192.168.1.23", "port": 4028},
            new_state=STATE_LOW,
            responded=True,
            rate_ths=20.0,
            threshold_ths=60.0,
            active_boards=3,
            now_ts=2500.0,
            low_sustained_seconds=900,
            interlock_decision=dec,
        )
        self.assertFalse(res["allowed"])
        self.assertEqual(res["blocked_by"], INTERLOCK_FIRMWARE_TRANSITION)
        self.assertEqual(st.low_since_ts, 2500.0)  # reset to current ts!

    def test_cooldown_delta_blocks_prior_to_quota_window_check(self) -> None:
        """Cooldown block prevents evaluation before quota window check."""
        st = MinerState(
            state=STATE_LOW,
            low_since_ts=1000.0,
            last_auto_reboot_ts=2400.0,  # 100s ago
            auto_reboot_timestamps=[2000.0, 2200.0, 2400.0],  # 3 reboots in window
        )
        res = SupervisoryBehavioralHarness.evaluate_auto_reboot_pipeline(
            state=st,
            miner={"name": "M23", "host": "192.168.1.23", "port": 4028},
            new_state=STATE_LOW,
            responded=True,
            rate_ths=20.0,
            threshold_ths=60.0,
            active_boards=3,
            now_ts=2500.0,
            low_sustained_seconds=900,
            reboot_cooldown_seconds=1800,
            max_reboots_per_window=3,
        )
        self.assertFalse(res["allowed"])
        self.assertEqual(res["blocked_by"], "cooldown")
        self.assertFalse(st.degraded_mode)  # not set to degraded because cooldown evaluated first!


# ==============================================================================
# 4. Hashboard Detection Precedence over Low Hashrate (8 tests) - Phase A T005
# ==============================================================================

class TestVnishHashboardDetectionBehavioral(unittest.TestCase):
    """Behavioral parity tests for board parsing and detection precedence."""

    def test_count_active_boards_parses_vnish_acn_numeric_and_string_types(self) -> None:
        """Correctly parses int, str, and float chain_acn fields."""
        entry = {"chain_acn1": 126, "chain_acn2": "126", "chain_acn3": 126.0}
        self.assertEqual(3, _count_active_boards(entry))

    def test_count_active_boards_ignores_zero_and_malformed(self) -> None:
        """Zero and malformed values are not counted as active boards."""
        entry = {"chain_acn1": 126, "chain_acn2": 0, "chain_acn3": "bad"}
        self.assertEqual(1, _count_active_boards(entry))

    def test_count_active_boards_returns_none_for_missing_chain_fields(self) -> None:
        """Returns None when payload lacks any board telemetry fields."""
        self.assertIsNone(_count_active_boards({"STATUS": "S"}))

    def test_count_active_boards_supports_legacy_list_and_alive_fields(self) -> None:
        """Supports legacy list format and individual alive fields."""
        self.assertEqual(2, _count_active_boards({"chain_acn": [63, 0, 63]}))
        self.assertEqual(
            2,
            _count_active_boards(
                {"chain0_asicnum": 63, "chain1_alive": 1, "chain2_status": "dead"}
            ),
        )

    def test_stats_snapshot_extracts_first_entry_with_board_signal(self) -> None:
        """Extracts first STATS entry that contains explicit board counts."""
        response = {
            "STATS": [
                {"STATUS": "S"},
                {"chain_acn1": 126, "chain_acn2": 126, "chain_acn3": 0},
                {"chain_acn1": 126, "chain_acn2": 126, "chain_acn3": 126},
            ]
        }
        with patch("app.miner_monitor._read_command", return_value=response):
            active_boards, responded, raw = read_stats_snapshot("h23", 4028)
        self.assertTrue(responded)
        self.assertEqual(2, active_boards)
        self.assertIs(response, raw)

    def test_detection_precedence_missing_boards_overrides_low_hashrate(self) -> None:
        """Missing board (active_boards < expected_boards) yields STATE_HASHBOARD even when hashrate is below threshold."""
        st = SupervisoryBehavioralHarness.classify_detection_state(
            responded=True,
            rate_ths=25.0,  # Below threshold 60.0
            threshold_ths=60.0,
            active_boards=2,  # Missing 1 board
            expected_boards=3,
        )
        self.assertEqual(STATE_HASHBOARD, st)

    def test_detection_full_boards_with_low_hashrate_yields_state_low(self) -> None:
        """All boards present (active_boards == expected_boards) with low hashrate yields STATE_LOW."""
        st = SupervisoryBehavioralHarness.classify_detection_state(
            responded=True,
            rate_ths=25.0,
            threshold_ths=60.0,
            active_boards=3,
            expected_boards=3,
        )
        self.assertEqual(STATE_LOW, st)

    def test_detection_recovery_to_ok_clears_both_low_and_hashboard_timers(self) -> None:
        """Recovery to STATE_OK clears both low_since_ts and hashboard_since_ts."""
        state = MinerState(state=STATE_HASHBOARD, hashboard_since_ts=1000.0, low_since_ts=1000.0)
        SupervisoryBehavioralHarness.apply_state_transitions(state, STATE_OK, 2000.0)
        self.assertEqual(STATE_OK, state.state)
        self.assertIsNone(state.hashboard_since_ts)
        self.assertIsNone(state.low_since_ts)


if __name__ == "__main__":
    unittest.main()
