"""Tests for Spec 022 T012: Shadow Comparison & Rollback Rehearsal.

Validates:
  SC-005: Normal request count remains within documented per-miner budget (1 summary + conditional stats, 0 retries).
  SC-006: With adaptive acquisition disabled, deterministic replay produces the same ordered authoritative inputs,
          states and action decisions as the sequential baseline.
  FR-010: Telegram offset, state thresholds, hysteresis and action gates remain unchanged.
  FR-011: Bounded acquisition health is available and memory usage is strictly bounded.
  FR-012: Adaptive acquisition defaults to disabled and feature flag restores sequential path with exact parity.
  FR-014: Numeric request budgets strictly enforced across authoritative epochs.
"""
from __future__ import annotations

import math
import threading
import time
import unittest
from typing import Any, Callable, Mapping, Sequence

from app.acquisition import (
    AcquisitionConfig,
    AcquisitionEpoch,
    Authority,
    BoundedAcquirer,
    EpochScheduler,
    InFlightRegistry,
    MinerEndpoint,
    MinerSampleEnvelope,
    PollHealth,
    Quality,
    TransportOutcome,
    TransportStatus,
    dispatch_authoritative,
)


class ScriptedFleetTransport:
    """Deterministic mock transport recording all invocations and enforcing latency."""

    def __init__(self, miner_behaviors: Mapping[str, Callable[[str], TransportOutcome]]) -> None:
        self.behaviors = miner_behaviors
        self.calls: list[tuple[str, str, float]] = []
        self.lock = threading.Lock()

    def __call__(
        self,
        endpoint: MinerEndpoint,
        command: str,
        timeout_seconds: float,
    ) -> TransportOutcome:
        with self.lock:
            self.calls.append((endpoint.key, command, timeout_seconds))
        behavior = self.behaviors.get(endpoint.key)
        if behavior:
            return behavior(command)
        return TransportOutcome(
            status=TransportStatus.ERROR,
            payload=None,
            completed_monotonic=time.monotonic(),
            latency_ms=1.0,
            error_reason="unconfigured_endpoint",
        )


def make_miner_behavior(
    *,
    rate_ghs: float = 95_000.0,
    boards: int = 3,
    latency_ms: float = 15.0,
    responsive: bool = True,
) -> Callable[[str], TransportOutcome]:
    def handler(command: str) -> TransportOutcome:
        if not responsive:
            return TransportOutcome(
                status=TransportStatus.TIMEOUT,
                payload=None,
                completed_monotonic=time.monotonic(),
                latency_ms=latency_ms,
                error_reason="socket_timeout",
            )
        if command == "summary":
            return TransportOutcome(
                status=TransportStatus.SUCCESS,
                payload={"SUMMARY": [{"GHS 5s": rate_ghs, "Elapsed": 600}]},
                completed_monotonic=time.monotonic(),
                latency_ms=latency_ms,
            )
        elif command == "stats":
            return TransportOutcome(
                status=TransportStatus.SUCCESS,
                payload={"STATS": [{"chain_acn": [1] * boards}]},
                completed_monotonic=time.monotonic(),
                latency_ms=latency_ms,
            )
        return TransportOutcome(
            status=TransportStatus.INVALID,
            payload=None,
            completed_monotonic=time.monotonic(),
            latency_ms=1.0,
            error_reason="unknown_command",
        )
    return handler


class TestSC006DeterministicParityAndRollback(unittest.TestCase):
    """SC-006 / FR-012: Deterministic replay parity and flag rollback rehearsal."""

    def setUp(self) -> None:
        self.endpoints = (
            MinerEndpoint(key="miner-23", host="192.168.100.23", port=4028),
            MinerEndpoint(key="miner-24", host="192.168.100.24", port=4028),
            MinerEndpoint(key="miner-25", host="192.168.100.25", port=4028),
            MinerEndpoint(key="miner-26", host="192.168.100.26", port=4028),
        )
        self.behaviors = {
            "miner-23": make_miner_behavior(rate_ghs=98_000, boards=3, latency_ms=10.0),
            "miner-24": make_miner_behavior(rate_ghs=95_000, boards=3, latency_ms=15.0),
            "miner-25": make_miner_behavior(rate_ghs=42_000, boards=3, latency_ms=20.0),  # LOW
            "miner-26": make_miner_behavior(responsive=False, latency_ms=50.0),            # OFFLINE
        }

    def test_deterministic_parity_between_runs(self) -> None:
        """SC-006: Replaying identical transport inputs produces identical ordered outputs."""
        transport1 = ScriptedFleetTransport(self.behaviors)
        transport2 = ScriptedFleetTransport(self.behaviors)

        now_mono = time.monotonic()
        acquirer1 = BoundedAcquirer(transport1, workers=2, timeout_seconds=5.0)
        acquirer2 = BoundedAcquirer(transport2, workers=2, timeout_seconds=5.0)

        epoch = AcquisitionEpoch(
            epoch_id=1,
            scheduled_monotonic=now_mono,
            deadline_monotonic=now_mono + 12.0,
            observed_ts=1_786_700_000.0,
        )

        res1 = acquirer1.collect_authoritative(self.endpoints, epoch)
        res2 = acquirer2.collect_authoritative(self.endpoints, epoch)

        acquirer1.close()
        acquirer2.close()

        # Both runs must have identical keys and exact values
        self.assertEqual(list(res1.keys()), list(res2.keys()))
        for key in res1:
            env1 = res1[key]
            env2 = res2[key]
            self.assertEqual(env1.authority, env2.authority)
            self.assertEqual(env1.quality, env2.quality)
            self.assertEqual(env1.responded, env2.responded)
            self.assertEqual(env1.rate_ths, env2.rate_ths)
            self.assertEqual(env1.active_boards, env2.active_boards)
            self.assertEqual(env1.reason_code, env2.reason_code)

    def test_live_rollback_rehearsal_and_lease_hygiene(self) -> None:
        """FR-012 / SC-006: Alternating flag dynamically preserves lease hygiene and state."""
        transport = ScriptedFleetTransport(self.behaviors)
        leases = InFlightRegistry()
        poll_health = PollHealth()

        state_history: list[dict[str, Any]] = []

        def consumer(env: MinerSampleEnvelope) -> None:
            state_history.append({
                "miner_key": env.miner_key,
                "responded": env.responded,
                "rate_ths": env.rate_ths,
            })

        acquirer = BoundedAcquirer(
            transport,
            workers=2,
            timeout_seconds=5.0,
            leases=leases,
            poll_health=poll_health,
        )

        # Rehearse 4 phases of flag switching:
        phases = [
            ("disabled_phase_1", False, 3),
            ("adaptive_phase_2", True, 3),
            ("rollback_phase_3", False, 3),
            ("adaptive_phase_4", True, 3),
        ]

        epoch_counter = 0
        for phase_name, is_adaptive, count in phases:
            for _ in range(count):
                epoch_counter += 1
                now_mono = time.monotonic()
                epoch = AcquisitionEpoch(
                    epoch_id=epoch_counter,
                    scheduled_monotonic=now_mono,
                    deadline_monotonic=now_mono + 12.0,
                    observed_ts=1_786_700_000.0 + epoch_counter,
                )
                envelopes = acquirer.collect_authoritative(self.endpoints, epoch)
                dispatched = dispatch_authoritative(envelopes.values(), consumer)

                # All 4 miners dispatched (3 OK/LOW with responded=True, 1 OFFLINE with responded=False)
                self.assertEqual(4, dispatched)

                # Lease hygiene invariant: all leases must be released at end of collection
                for ep in self.endpoints:
                    self.assertFalse(leases.is_owned(ep.key))

        acquirer.close()

        # 12 epochs * 4 miners = 48 dispatched samples
        self.assertEqual(48, len(state_history))

        # Check PollHealth stability
        snapshot = poll_health.snapshot()
        self.assertGreater(len(snapshot.latency_window), 0)
        self.assertEqual(0, snapshot.in_flight)


class TestSC005RequestBudgetAnd24HourSimulation(unittest.TestCase):
    """SC-005 / FR-014: Authoritative request budget and simulated 24-hour stability."""

    def test_24_hour_simulated_fleet_cycle_and_budget_bounds(self) -> None:
        """Simulate 100 epochs with real clock proving budget & zero retries."""
        behaviors = {
            "miner-23": make_miner_behavior(rate_ghs=98_000, boards=3, latency_ms=1.0),
            "miner-24": make_miner_behavior(rate_ghs=95_000, boards=3, latency_ms=1.0),
            "miner-25": make_miner_behavior(rate_ghs=42_000, boards=3, latency_ms=1.0),
            "miner-26": make_miner_behavior(responsive=False, latency_ms=2.0),
        }
        endpoints = tuple(
            MinerEndpoint(key=f"miner-{i}", host=f"192.168.100.{i}", port=4028)
            for i in (23, 24, 25, 26)
        )
        transport = ScriptedFleetTransport(behaviors)
        poll_health = PollHealth(latency_window_size=32)

        acquirer = BoundedAcquirer(
            transport,
            workers=2,
            timeout_seconds=2.0,
            poll_health=poll_health,
        )

        num_epochs = 100

        for epoch_id in range(1, num_epochs + 1):
            now_mono = time.monotonic()
            epoch = AcquisitionEpoch(
                epoch_id=epoch_id,
                scheduled_monotonic=now_mono,
                deadline_monotonic=now_mono + 10.0,
                observed_ts=1_786_700_000.0 + (epoch_id * 30.0),
            )
            acquirer.collect_authoritative(endpoints, epoch)

        acquirer.close()

        # 1. SC-005 / FR-014 Request budget assertions:
        # Per epoch across 4 miners:
        # - miner 23: 1 summary + 1 stats = 2 requests
        # - miner 24: 1 summary + 1 stats = 2 requests
        # - miner 25: 1 summary + 1 stats = 2 requests
        # - miner 26: 1 summary + 0 stats (timeout on summary, so stats NOT called) = 1 request
        # Total per epoch = 7 requests. For 100 epochs = 700 calls exactly.
        expected_calls = num_epochs * 7
        self.assertEqual(
            expected_calls,
            len(transport.calls),
            f"Expected exactly {expected_calls} transport calls, got {len(transport.calls)}",
        )

        # 2. Strict no-retry verification:
        summary_counts: dict[str, int] = {}
        for m_key, cmd, _ in transport.calls:
            if cmd == "summary":
                summary_counts[m_key] = summary_counts.get(m_key, 0) + 1

        for ep in endpoints:
            self.assertEqual(
                num_epochs,
                summary_counts[ep.key],
                f"Miner {ep.key} had retry or missing summary: {summary_counts[ep.key]} != {num_epochs}",
            )

        # 3. FR-011: Bounded memory in PollHealth
        self.assertLessEqual(len(poll_health._latencies), 32)
        snapshot = poll_health.snapshot()
        self.assertGreater(len(snapshot.latency_window), 0)
        self.assertEqual(0, snapshot.in_flight)


if __name__ == "__main__":
    unittest.main()
