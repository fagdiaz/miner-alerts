"""Tests for Spec 022 T009 & T011.

T009 — Diagnostic data read-only context exposure:
    Formally proves that DiagnosticProbeResult / EpisodeDiagnosticEnvelope
    and collect_diagnostic envelopes are structurally isolated from the
    authoritative consumer path.  They cannot mutate miner_states, streak
    counters, reboot eligibility or the polling loop.

T011 — Pre-rollout action/state invariant validation:
    Verifies state, action, Telegram-offset and startup-guard invariants
    through static inspection and deterministic unit contracts.

FR-005, FR-006, SC-003, SC-004 (T009)
SC-001, SC-002, SC-006, SC-007   (T011)
"""
from __future__ import annotations

import inspect
import threading
import time
import types
import unittest
from typing import Any, Optional

from app.acquisition import (
    AcquisitionConfig,
    Authority,
    BoundedAcquirer,
    DiagnosticProbeResult,
    EpisodeDiagnosticEnvelope,
    InFlightRegistry,
    MinerEndpoint,
    MinerSampleEnvelope,
    PollHealth,
    Quality,
    TransportOutcome,
    TransportStatus,
    dispatch_authoritative,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _base_envelope(
    *,
    miner_key: str = "miner-a",
    authority: Authority = Authority.AUTHORITATIVE,
    quality: Quality = Quality.VALID,
    reason_code: str = "ok",
    rate_ths: float = 90.0,
) -> MinerSampleEnvelope:
    return MinerSampleEnvelope(
        miner_key=miner_key,
        authority=authority,
        epoch_id=1,
        observed_ts=1_000.0,
        completed_monotonic=100.0,
        latency_ms=5.0,
        responded=True,
        rate_ths=rate_ths,
        elapsed_seconds=600,
        active_boards=3,
        quality=quality,
        reason_code=reason_code,
        summary_entry=None,
        stats_response=None,
        summary_requests=1,
        stats_requests=1,
    )


def _stub_transport(
    outcome: TransportOutcome,
) -> Any:
    """Return a callable transport that always returns the given outcome."""
    def _t(endpoint: MinerEndpoint, command: str, timeout_seconds: float) -> TransportOutcome:
        return outcome
    return _t


# ---------------------------------------------------------------------------
# T009 — Read-Only Context Isolation Tests
# ---------------------------------------------------------------------------

class TestDiagnosticReadOnlyIsolation(unittest.TestCase):
    """T009: Diagnostic data must feed only read-only contexts.

    DiagnosticProbeResult / EpisodeDiagnosticEnvelope cannot alter
    miner_states, streak counters, reboot eligibility or the authoritative
    consumer callback.
    """

    # --- Structural immutability ---

    def test_diagnostic_probe_result_is_frozen(self) -> None:
        """DiagnosticProbeResult must be immutable (frozen dataclass)."""
        probe = DiagnosticProbeResult(
            miner_key="miner-a",
            command="summary",
            status=TransportStatus.SUCCESS,
        )
        with self.assertRaises(AttributeError):
            probe.miner_key = "mutated"  # type: ignore[misc]

    def test_episode_diagnostic_envelope_is_frozen(self) -> None:
        """EpisodeDiagnosticEnvelope must be immutable (frozen dataclass)."""
        env = EpisodeDiagnosticEnvelope(
            episode_id="ep:1",
            miner_key="miner-a",
        )
        with self.assertRaises(AttributeError):
            env.miner_key = "mutated"  # type: ignore[misc]

    def test_episode_envelope_probe_results_are_tuple_not_list(self) -> None:
        """probe_results must be a tuple — cannot be appended to in-place."""
        probe = DiagnosticProbeResult(
            miner_key="miner-a",
            command="summary",
            status=TransportStatus.TIMEOUT,
        )
        env = EpisodeDiagnosticEnvelope(
            episode_id="ep:2",
            miner_key="miner-a",
            probe_results=(probe,),
        )
        self.assertIsInstance(env.probe_results, tuple)
        with self.assertRaises(AttributeError):
            env.probe_results.append(probe)  # type: ignore[attr-defined]

    # --- Authority boundary ---

    def test_collect_diagnostic_produces_diagnostic_authority_envelopes(self) -> None:
        """BoundedAcquirer.collect_diagnostic must tag all envelopes DIAGNOSTIC."""
        success_payload = {
            "SUMMARY": [{"GHS 5s": "90.0", "Elapsed": 600}]
        }
        transport = _stub_transport(
            TransportOutcome(
                status=TransportStatus.SUCCESS,
                payload=success_payload,
                completed_monotonic=time.monotonic(),
                latency_ms=10.0,
            )
        )
        acquirer = BoundedAcquirer(transport, workers=1, timeout_seconds=5.0)
        try:
            result = acquirer.collect_diagnostic(
                [MinerEndpoint(key="miner-a", host="127.0.0.1", port=9999)],
                diagnostic_id=1,
                observed_ts=time.time(),
                deadline_monotonic=time.monotonic() + 10.0,
            )
        finally:
            acquirer.close()

        self.assertEqual(1, len(result))
        env = result["miner-a"]
        self.assertIs(
            Authority.DIAGNOSTIC,
            env.authority,
            "collect_diagnostic must produce DIAGNOSTIC authority envelopes",
        )

    def test_diagnostic_envelope_blocked_by_dispatch_authoritative(self) -> None:
        """dispatch_authoritative must filter out DIAGNOSTIC envelopes entirely."""
        diag_env = _base_envelope(
            authority=Authority.DIAGNOSTIC,
            quality=Quality.VALID,
        )
        auth_env = _base_envelope(
            authority=Authority.AUTHORITATIVE,
            quality=Quality.VALID,
        )

        reached: list[str] = []
        count = dispatch_authoritative(
            [diag_env, auth_env],
            lambda e: reached.append(e.miner_key),
        )

        self.assertEqual(1, count)
        self.assertEqual(["miner-a"], reached)

    def test_late_diagnostic_envelope_also_blocked(self) -> None:
        """DIAGNOSTIC+LATE envelopes must also be filtered by dispatch_authoritative."""
        diag_late = _base_envelope(
            authority=Authority.DIAGNOSTIC,
            quality=Quality.LATE,
            reason_code="epoch_deadline_exceeded",
        )
        reached: list[str] = []
        count = dispatch_authoritative([diag_late], lambda e: reached.append(e.miner_key))
        self.assertEqual(0, count)
        self.assertEqual([], reached)

    def test_dispatch_authoritative_does_not_mutate_external_state(self) -> None:
        """dispatch_authoritative is a pure filter — it must not mutate any dict."""
        miner_states: dict[str, str] = {"miner-a": "OK"}
        snapshot_before = dict(miner_states)

        diag_env = _base_envelope(authority=Authority.DIAGNOSTIC, quality=Quality.VALID)
        dispatch_authoritative([diag_env], lambda e: None)

        self.assertEqual(snapshot_before, miner_states,
                         "dispatch_authoritative must not modify miner_states")

    def test_diagnostics_disabled_when_main_flag_off(self) -> None:
        """diagnostics_enabled must be False whenever adaptive_acquisition_enabled=False."""
        config_off = {
            "adaptive_acquisition_enabled": False,
            "adaptive_diagnostics_enabled": True,  # explicitly requested but main is off
        }
        acq_cfg, _ = AcquisitionConfig.from_mapping(config_off)
        self.assertFalse(acq_cfg.diagnostics_enabled,
                         "diagnostics_enabled must remain False when main flag is off")

    def test_diagnostics_require_both_flags_true(self) -> None:
        """diagnostics_enabled is True only when both flags are True."""
        config_both = {
            "adaptive_acquisition_enabled": True,
            "adaptive_diagnostics_enabled": True,
        }
        acq_cfg, _ = AcquisitionConfig.from_mapping(config_both)
        self.assertTrue(acq_cfg.diagnostics_enabled)

    def test_diagnostic_envelope_carries_no_action_field(self) -> None:
        """DiagnosticProbeResult must carry no fields for reboot/action decisions."""
        forbidden_fields = {
            "allow_reboot", "trigger_reboot", "auto_action",
            "reboot_eligible", "external_cli_command",
        }
        probe = DiagnosticProbeResult(
            miner_key="miner-a",
            command="summary",
            status=TransportStatus.SUCCESS,
        )
        for field_name in forbidden_fields:
            self.assertFalse(
                hasattr(probe, field_name),
                f"DiagnosticProbeResult must not have field '{field_name}'",
            )

    def test_episode_envelope_carries_no_action_field(self) -> None:
        """EpisodeDiagnosticEnvelope must carry no fields for reboot/action decisions."""
        forbidden_fields = {
            "allow_reboot", "trigger_reboot", "auto_action",
            "reboot_eligible", "external_cli_command",
        }
        env = EpisodeDiagnosticEnvelope(
            episode_id="ep:99",
            miner_key="miner-a",
        )
        for field_name in forbidden_fields:
            self.assertFalse(
                hasattr(env, field_name),
                f"EpisodeDiagnosticEnvelope must not have field '{field_name}'",
            )

    def test_diagnostic_budget_is_summary_only(self) -> None:
        """Diagnostic envelopes must issue exactly 1 summary request and 0 stats."""
        success_payload = {
            "SUMMARY": [{"GHS 5s": "90.0", "Elapsed": 600}]
        }
        transport = _stub_transport(
            TransportOutcome(
                status=TransportStatus.SUCCESS,
                payload=success_payload,
                completed_monotonic=time.monotonic(),
                latency_ms=5.0,
            )
        )
        acquirer = BoundedAcquirer(transport, workers=1, timeout_seconds=5.0)
        try:
            result = acquirer.collect_diagnostic(
                [MinerEndpoint(key="miner-a", host="127.0.0.1", port=9999)],
                diagnostic_id=1,
                observed_ts=time.time(),
                deadline_monotonic=time.monotonic() + 10.0,
            )
        finally:
            acquirer.close()

        env = result["miner-a"]
        self.assertEqual(1, env.summary_requests,
                         "Diagnostic must issue exactly 1 summary request")
        self.assertEqual(0, env.stats_requests,
                         "Diagnostic must issue 0 stats requests")

    def test_diagnostic_does_not_update_poll_health(self) -> None:
        """collect_diagnostic must NOT call poll_health.record_epoch (read-only)."""
        recorded: list[bool] = []

        class _SpyPollHealth(PollHealth):
            def record_epoch(self, epoch, envelopes):  # type: ignore[override]
                recorded.append(True)
                super().record_epoch(epoch, envelopes)

        spy = _SpyPollHealth()
        transport = _stub_transport(
            TransportOutcome(
                status=TransportStatus.TIMEOUT,
                completed_monotonic=time.monotonic(),
                latency_ms=5000.0,
            )
        )
        acquirer = BoundedAcquirer(
            transport,
            workers=1,
            timeout_seconds=5.0,
            poll_health=spy,
        )
        try:
            acquirer.collect_diagnostic(
                [MinerEndpoint(key="miner-a", host="127.0.0.1", port=9999)],
                diagnostic_id=2,
                observed_ts=time.time(),
                deadline_monotonic=time.monotonic() + 10.0,
            )
        finally:
            acquirer.close()

        self.assertEqual(
            [], recorded,
            "collect_diagnostic must NOT call record_epoch (read-only isolation)",
        )


# ---------------------------------------------------------------------------
# T011 — Pre-Rollout Invariant Validation
# ---------------------------------------------------------------------------

class TestStateInvariant(unittest.TestCase):
    """T011 SC-001/SC-002: State transitions must be identical between adaptive
    and sequential paths through dispatch_authoritative filtering."""

    def test_dispatch_authoritative_only_applies_valid_authoritative_envelopes(self) -> None:
        """Exactly the valid AUTHORITATIVE non-LATE envelopes reach the consumer."""
        envelopes = [
            _base_envelope(miner_key="m1", authority=Authority.AUTHORITATIVE, quality=Quality.VALID),
            _base_envelope(miner_key="m2", authority=Authority.DIAGNOSTIC, quality=Quality.VALID),
            _base_envelope(miner_key="m3", authority=Authority.AUTHORITATIVE, quality=Quality.LATE),
            _base_envelope(miner_key="m4", authority=Authority.AUTHORITATIVE, quality=Quality.TIMEOUT),
            _base_envelope(miner_key="m5", authority=Authority.AUTHORITATIVE, quality=Quality.INVALID),
            _base_envelope(miner_key="m6", authority=Authority.AUTHORITATIVE, quality=Quality.VALID),
        ]
        applied: list[str] = []
        count = dispatch_authoritative(envelopes, lambda e: applied.append(e.miner_key))

        # Only m1 and m6 are AUTHORITATIVE + non-LATE
        self.assertEqual(4, count)
        self.assertIn("m1", applied)
        self.assertNotIn("m2", applied)  # DIAGNOSTIC
        self.assertNotIn("m3", applied)  # LATE
        self.assertIn("m4", applied)     # TIMEOUT is not LATE — still reaches consumer
        self.assertIn("m5", applied)     # INVALID same
        self.assertIn("m6", applied)

    def test_disabled_config_produces_no_adaptive_paths(self) -> None:
        """With adaptive_acquisition_enabled=False, both main and diagnostic paths are off."""
        cfg, warnings = AcquisitionConfig.from_mapping({
            "adaptive_acquisition_enabled": False,
        })
        self.assertFalse(cfg.enabled)
        self.assertFalse(cfg.diagnostics_enabled)
        self.assertEqual([], list(warnings))


class TestActionInvariant(unittest.TestCase):
    """T011 SC-006: Acquisition module must contain zero direct reboot/action calls."""

    def test_acquisition_module_has_no_hashcore_calls(self) -> None:
        """acquisition.py must not import or call Hashcore CLI or reboot functions."""
        import app.acquisition as acq_module
        source = inspect.getsource(acq_module)

        self.assertNotIn("hashcore", source.lower(),
                         "acquisition.py must not reference hashcore")
        self.assertNotIn("subprocess", source,
                         "acquisition.py must not use subprocess")
        self.assertNotIn("os.system", source,
                         "acquisition.py must not use os.system")

    def test_acquisition_module_has_no_miner_state_mutation(self) -> None:
        """acquisition.py must not write to miner_states, streaks or reboot counters."""
        import app.acquisition as acq_module
        source = inspect.getsource(acq_module)

        forbidden = [
            "miner_states",
            "reboot_count",
            "streak",
            "low_start_ts",
            "startup_guard",
            "send_telegram",
        ]
        for token in forbidden:
            self.assertNotIn(
                token,
                source,
                f"acquisition.py must not reference '{token}' (state/action mutation)",
            )

    def test_dispatch_authoritative_is_pure_filter(self) -> None:
        """dispatch_authoritative must return a count and invoke callback exactly once per allowed envelope."""
        call_log: list[str] = []
        envelopes = [
            _base_envelope(miner_key="m1", authority=Authority.AUTHORITATIVE, quality=Quality.VALID),
            _base_envelope(miner_key="m2", authority=Authority.AUTHORITATIVE, quality=Quality.VALID),
        ]
        count = dispatch_authoritative(envelopes, lambda e: call_log.append(e.miner_key))
        self.assertEqual(2, count)
        self.assertEqual(["m1", "m2"], call_log)


class TestTelegramOffsetInvariant(unittest.TestCase):
    """T011 SC-007: Adaptive acquisition must not alter Telegram polling offsets."""

    def test_acquisition_module_does_not_import_telegram_functions(self) -> None:
        """acquisition.py must not import or call any Telegram API functions."""
        import app.acquisition as acq_module
        source = inspect.getsource(acq_module)

        telegram_markers = [
            "send_telegram",
            "bot_token",
            "chat_id",
            "getUpdates",
            "sendMessage",
            "telegram",
            "update_id",
        ]
        for marker in telegram_markers:
            self.assertNotIn(
                marker,
                source,
                f"acquisition.py must not reference Telegram symbol '{marker}'",
            )


class TestStartupGuardInvariant(unittest.TestCase):
    """T011 SC-002: Startup guard timing must not be affected by acquisition config."""

    def test_acquisition_config_has_no_startup_guard_fields(self) -> None:
        """AcquisitionConfig must not contain startup_guard or grace_period fields."""
        forbidden = {
            "startup_guard_enabled",
            "startup_guard_seconds",
            "grace_period_seconds",
            "initial_grace",
        }
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(AcquisitionConfig)}
        overlap = forbidden & field_names
        self.assertEqual(
            set(), overlap,
            f"AcquisitionConfig must not contain startup/guard fields: {overlap}",
        )

    def test_disabled_acquisition_config_safe_defaults_unchanged(self) -> None:
        """Default AcquisitionConfig() must be disabled with safe numeric values."""
        cfg = AcquisitionConfig()
        self.assertFalse(cfg.enabled)
        self.assertFalse(cfg.diagnostics_enabled)
        self.assertGreaterEqual(cfg.timeout_seconds, 1.0)
        self.assertLessEqual(cfg.timeout_seconds, 10.0)
        self.assertGreaterEqual(cfg.deadline_seconds, cfg.timeout_seconds)
        self.assertIn(cfg.workers, range(1, 5))


class TestNumericRequestBudgetInvariant(unittest.TestCase):
    """T011 FR-014/SC-005: Request budgets must be bounded and respected."""

    def test_authoritative_envelope_summary_and_stats_budget(self) -> None:
        """Authoritative path: exactly 1 summary + 1 stats per responsive miner."""
        env_valid = _base_envelope(
            authority=Authority.AUTHORITATIVE,
            quality=Quality.VALID,
        )
        # Default _base_envelope sets summary_requests=1, stats_requests=1
        self.assertEqual(1, env_valid.summary_requests)
        self.assertEqual(1, env_valid.stats_requests)

    def test_diagnostic_envelope_budget_is_summary_only_zero_stats(self) -> None:
        """Diagnostic envelopes carry summary_only budget (1 summary, 0 stats)."""
        success_payload = {"SUMMARY": [{"GHS 5s": "85.0", "Elapsed": 300}]}
        transport = _stub_transport(
            TransportOutcome(
                status=TransportStatus.SUCCESS,
                payload=success_payload,
                completed_monotonic=time.monotonic(),
                latency_ms=3.0,
            )
        )
        acquirer = BoundedAcquirer(transport, workers=1, timeout_seconds=5.0)
        try:
            result = acquirer.collect_diagnostic(
                [MinerEndpoint(key="miner-b", host="127.0.0.1", port=9999)],
                diagnostic_id=10,
                observed_ts=time.time(),
                deadline_monotonic=time.monotonic() + 10.0,
            )
        finally:
            acquirer.close()
        env = result["miner-b"]
        self.assertEqual(1, env.summary_requests)
        self.assertEqual(0, env.stats_requests)

    def test_workers_cap_is_enforced(self) -> None:
        """BoundedAcquirer must reject workers outside [1, 4]."""
        transport = _stub_transport(
            TransportOutcome(status=TransportStatus.TIMEOUT, completed_monotonic=0.0)
        )
        with self.assertRaises(ValueError):
            BoundedAcquirer(transport, workers=0, timeout_seconds=5.0)
        with self.assertRaises(ValueError):
            BoundedAcquirer(transport, workers=5, timeout_seconds=5.0)


if __name__ == "__main__":
    unittest.main()
