import math
import json
import threading
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from app.acquisition import (
    AcquisitionConfig,
    AcquisitionEpoch,
    Api4028Transport,
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


def summary_payload(rate_ghs: object = 95_000, elapsed: object = 600) -> dict:
    return {"SUMMARY": [{"GHS 5s": rate_ghs, "Elapsed": elapsed}]}


def stats_payload(boards: int = 3) -> dict:
    return {"STATS": [{"chain_acn": [1] * boards}]}


def outcome(
    payload: dict | None = None,
    *,
    status: TransportStatus = TransportStatus.SUCCESS,
    completed: float = 101.0,
    latency_ms: float = 10.0,
) -> TransportOutcome:
    return TransportOutcome(
        status=status,
        payload=payload,
        completed_monotonic=completed,
        latency_ms=latency_ms,
    )


class ScriptedTransport:
    def __init__(self, scripts: dict[tuple[str, str], object]) -> None:
        self.scripts = scripts
        self.calls: list[tuple[str, str, float]] = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(
        self,
        endpoint: MinerEndpoint,
        command: str,
        timeout_seconds: float,
    ) -> TransportOutcome:
        with self.lock:
            self.calls.append((endpoint.key, command, timeout_seconds))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            scripted = self.scripts[(endpoint.key, command)]
            if callable(scripted):
                return scripted()
            return scripted  # type: ignore[return-value]
        finally:
            with self.lock:
                self.active -= 1


class AcquisitionConfigTests(unittest.TestCase):
    def test_absent_and_explicit_disabled_use_safe_defaults(self) -> None:
        for raw in ({}, {"adaptive_acquisition_enabled": False}):
            with self.subTest(raw=raw):
                config, warnings = AcquisitionConfig.from_mapping(raw)
                self.assertFalse(config.enabled)
                self.assertFalse(config.diagnostics_enabled)
                self.assertEqual(2, config.workers)
                self.assertEqual(5.0, config.timeout_seconds)
                self.assertEqual(12.0, config.deadline_seconds)
                self.assertEqual((), warnings)

    def test_invalid_values_fall_back_with_sanitized_key_only_warnings(self) -> None:
        raw = {
            "adaptive_acquisition_enabled": "yes-secret",
            "adaptive_acquisition_workers": 99,
            "adaptive_acquisition_timeout_seconds": math.inf,
            "adaptive_acquisition_deadline_seconds": 0,
            "adaptive_diagnostics_enabled": True,
            "adaptive_diagnostic_interval_seconds": 1,
        }

        config, warnings = AcquisitionConfig.from_mapping(raw)

        self.assertFalse(config.enabled)
        self.assertFalse(config.diagnostics_enabled)
        self.assertEqual((2, 5.0, 12.0, 10.0), (
            config.workers,
            config.timeout_seconds,
            config.deadline_seconds,
            config.diagnostic_interval_seconds,
        ))
        self.assertEqual(5, len(warnings))
        self.assertTrue(all("yes-secret" not in warning for warning in warnings))
        self.assertTrue(all(warning.startswith("invalid_config key=") for warning in warnings))


class Api4028TransportTests(unittest.TestCase):
    class FakeSocket:
        def __init__(self, chunks: list[bytes]) -> None:
            self.chunks = list(chunks)
            self.sent = b""

        def __enter__(self) -> "Api4028TransportTests.FakeSocket":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def sendall(self, payload: bytes) -> None:
            self.sent = payload

        def recv(self, _size: int) -> bytes:
            return self.chunks.pop(0) if self.chunks else b""

    def test_success_empty_invalid_json_timeout_and_error_are_typed(self) -> None:
        endpoint = MinerEndpoint("miner-a", "example.invalid", 4028)
        transport = Api4028Transport(clock=lambda: 100.0)
        scenarios = (
            ([json.dumps(summary_payload()).encode(), b""], None, TransportStatus.SUCCESS),
            ([b""], None, TransportStatus.EMPTY),
            ([b"{broken", b""], None, TransportStatus.INVALID_JSON),
            (None, TimeoutError("secret endpoint"), TransportStatus.TIMEOUT),
            (None, OSError("secret endpoint"), TransportStatus.ERROR),
        )
        for chunks, error, expected in scenarios:
            with self.subTest(expected=expected):
                fake_socket = self.FakeSocket(chunks or [])
                side_effect = error if error is not None else None
                with mock.patch(
                    "app.acquisition.socket.create_connection",
                    side_effect=side_effect,
                    return_value=fake_socket,
                ):
                    result = transport(endpoint, "summary", 5.0)
                self.assertEqual(expected, result.status)
                self.assertFalse(hasattr(result, "error_message"))

    def test_only_scheduled_commands_are_accepted_before_socket_io(self) -> None:
        endpoint = MinerEndpoint("miner-a", "example.invalid", 4028)
        transport = Api4028Transport()
        with mock.patch("app.acquisition.socket.create_connection") as connect:
            with self.assertRaises(ValueError):
                transport(endpoint, "reboot", 5.0)
        connect.assert_not_called()


class EpochSchedulerTests(unittest.TestCase):
    def test_resume_skips_missed_epochs_without_catch_up(self) -> None:
        scheduler = EpochScheduler(period_seconds=30.0)
        first = scheduler.next_epoch(now_monotonic=100.0, observed_ts=1_000.0, deadline_seconds=12.0)
        resumed = scheduler.next_epoch(now_monotonic=250.0, observed_ts=1_150.0, deadline_seconds=12.0)

        self.assertEqual(1, first.epoch_id)
        self.assertEqual(2, resumed.epoch_id)
        self.assertEqual(250.0, resumed.scheduled_monotonic)
        self.assertEqual(4, scheduler.skipped_epoch_count)

    def test_current_epoch_is_not_backed_off_after_failure(self) -> None:
        scheduler = EpochScheduler(period_seconds=30.0)
        scheduler.next_epoch(100.0, 1_000.0, 12.0)

        self.assertIsNone(scheduler.next_epoch(129.9, 1_029.9, 12.0))
        next_epoch = scheduler.next_epoch(130.0, 1_030.0, 12.0)

        self.assertIsNotNone(next_epoch)
        self.assertEqual(2, next_epoch.epoch_id)


class AuthoritativeAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.miners = tuple(
            MinerEndpoint(key=f"miner-{letter}", host="example.invalid", port=4028)
            for letter in "abcd"
        )

    def epoch(self, *, deadline: float = 112.0) -> AcquisitionEpoch:
        return AcquisitionEpoch(
            epoch_id=7,
            scheduled_monotonic=100.0,
            deadline_monotonic=deadline,
            observed_ts=1_000.0,
        )

    def test_completion_order_never_changes_configured_order(self) -> None:
        release_a = threading.Event()
        b_done = threading.Event()

        def slow_a() -> TransportOutcome:
            release_a.wait(1.0)
            return outcome(summary_payload(), completed=100.8)

        def fast_b() -> TransportOutcome:
            b_done.set()
            return outcome(summary_payload(), completed=100.4)

        scripts: dict[tuple[str, str], object] = {}
        for miner in self.miners:
            scripts[(miner.key, "summary")] = outcome(summary_payload(), completed=101.0)
            scripts[(miner.key, "stats")] = outcome(stats_payload(), completed=101.1)
        scripts[("miner-a", "summary")] = slow_a
        scripts[("miner-b", "summary")] = fast_b
        transport = ScriptedTransport(scripts)
        acquirer = BoundedAcquirer(
            transport, workers=2, timeout_seconds=5.0, clock=lambda: 100.0
        )
        result_box: list[dict[str, MinerSampleEnvelope]] = []
        thread = threading.Thread(
            target=lambda: result_box.append(acquirer.collect_authoritative(self.miners, self.epoch())),
            daemon=True,
        )

        thread.start()
        self.assertTrue(b_done.wait(1.0))
        release_a.set()
        thread.join(2.0)
        acquirer.close()

        self.assertFalse(thread.is_alive())
        self.assertEqual([m.key for m in self.miners], list(result_box[0]))
        self.assertLessEqual(transport.max_active, 2)

    def test_one_timeout_does_not_drop_peer_envelopes_or_retry(self) -> None:
        scripts: dict[tuple[str, str], object] = {}
        for miner in self.miners:
            scripts[(miner.key, "summary")] = outcome(summary_payload())
            scripts[(miner.key, "stats")] = outcome(stats_payload())
        scripts[("miner-b", "summary")] = outcome(
            status=TransportStatus.TIMEOUT,
            completed=105.0,
        )
        transport = ScriptedTransport(scripts)
        acquirer = BoundedAcquirer(
            transport, workers=2, timeout_seconds=5.0, clock=lambda: 100.0
        )

        envelopes = acquirer.collect_authoritative(self.miners, self.epoch())
        acquirer.close()

        self.assertEqual(Quality.TIMEOUT, envelopes["miner-b"].quality)
        self.assertEqual("transport_timeout", envelopes["miner-b"].reason_code)
        self.assertEqual(4, sum(item.summary_requests for item in envelopes.values()))
        self.assertEqual(3, sum(item.stats_requests for item in envelopes.values()))
        self.assertEqual(1, Counter(call[:2] for call in transport.calls)[("miner-b", "summary")])
        self.assertNotIn(("miner-b", "stats"), [call[:2] for call in transport.calls])
        self.assertTrue(all(key in envelopes for key in (m.key for m in self.miners)))

    def test_one_blocked_worker_does_not_head_of_line_block_three_peers(self) -> None:
        slow_release = threading.Event()
        slow_started = threading.Event()
        peers_done = threading.Event()
        peer_count = 0
        peer_lock = threading.Lock()

        def blocked_timeout() -> TransportOutcome:
            slow_started.set()
            slow_release.wait(2.0)
            return outcome(status=TransportStatus.TIMEOUT, completed=105.0)

        def peer_summary() -> TransportOutcome:
            nonlocal peer_count
            with peer_lock:
                peer_count += 1
                if peer_count == 3:
                    peers_done.set()
            return outcome(summary_payload(), completed=101.0)

        scripts: dict[tuple[str, str], object] = {
            ("miner-a", "summary"): blocked_timeout,
        }
        for miner in self.miners[1:]:
            scripts[(miner.key, "summary")] = peer_summary
            scripts[(miner.key, "stats")] = outcome(stats_payload(), completed=101.5)
        transport = ScriptedTransport(scripts)
        acquirer = BoundedAcquirer(
            transport, workers=2, timeout_seconds=5.0, clock=lambda: 100.0
        )
        result_box: list[dict[str, MinerSampleEnvelope]] = []
        thread = threading.Thread(
            target=lambda: result_box.append(
                acquirer.collect_authoritative(self.miners, self.epoch())
            ),
            daemon=True,
        )

        thread.start()
        self.assertTrue(slow_started.wait(1.0))
        self.assertTrue(peers_done.wait(1.0))
        self.assertFalse(slow_release.is_set())
        slow_release.set()
        thread.join(2.0)
        acquirer.close()

        self.assertFalse(thread.is_alive())
        self.assertEqual(Quality.TIMEOUT, result_box[0]["miner-a"].quality)
        self.assertTrue(
            all(result_box[0][miner.key].quality is Quality.VALID for miner in self.miners[1:])
        )
        self.assertLessEqual(transport.max_active, 2)

    def test_partial_stats_and_non_finite_rate_are_explicit(self) -> None:
        miners = self.miners[:2]
        transport = ScriptedTransport({
            ("miner-a", "summary"): outcome(summary_payload()),
            ("miner-a", "stats"): outcome({"STATS": [{}]}),
            ("miner-b", "summary"): outcome(summary_payload(float("nan"))),
        })
        acquirer = BoundedAcquirer(
            transport, workers=2, timeout_seconds=5.0, clock=lambda: 100.0
        )

        envelopes = acquirer.collect_authoritative(miners, self.epoch())
        acquirer.close()

        self.assertEqual((Quality.PARTIAL, "stats_missing"), (
            envelopes["miner-a"].quality,
            envelopes["miner-a"].reason_code,
        ))
        self.assertTrue(envelopes["miner-a"].responded)
        self.assertIsNone(envelopes["miner-a"].active_boards)
        self.assertEqual((Quality.INVALID, "rate_invalid"), (
            envelopes["miner-b"].quality,
            envelopes["miner-b"].reason_code,
        ))
        self.assertIsNone(envelopes["miner-b"].rate_ths)
        self.assertEqual(0, envelopes["miner-b"].stats_requests)

    def test_legacy_chain_board_keys_preserve_current_stats_compatibility(self) -> None:
        miner = self.miners[0]
        transport = ScriptedTransport({
            (miner.key, "summary"): outcome(summary_payload()),
            (miner.key, "stats"): outcome({
                "STATS": [{"chain_acn0": 1, "chain_acn1": 1, "chain_acn2": 1}]
            }),
        })
        acquirer = BoundedAcquirer(
            transport, workers=1, timeout_seconds=5.0, clock=lambda: 100.0
        )

        envelope = acquirer.collect_authoritative((miner,), self.epoch())[miner.key]
        acquirer.close()

        self.assertEqual(Quality.VALID, envelope.quality)
        self.assertEqual(3, envelope.active_boards)

    def test_late_result_is_never_authoritative_for_application(self) -> None:
        miner = self.miners[0]
        transport = ScriptedTransport({
            (miner.key, "summary"): outcome(summary_payload(), completed=112.1),
            (miner.key, "stats"): outcome(stats_payload(), completed=112.2),
        })
        acquirer = BoundedAcquirer(
            transport, workers=1, timeout_seconds=5.0, clock=lambda: 100.0
        )

        envelope = acquirer.collect_authoritative((miner,), self.epoch())[miner.key]
        acquirer.close()

        self.assertEqual(Quality.LATE, envelope.quality)
        self.assertEqual("epoch_deadline_exceeded", envelope.reason_code)
        applied: list[str] = []
        dispatch_authoritative((envelope,), lambda item: applied.append(item.miner_key))
        self.assertEqual([], applied)

    def test_existing_lease_returns_overlap_without_transport(self) -> None:
        miner = self.miners[0]
        leases = InFlightRegistry()
        lease = leases.acquire(miner.key, Authority.DIAGNOSTIC, 6, 90.0, 120.0)
        self.assertIsNotNone(lease)
        transport = ScriptedTransport({})
        acquirer = BoundedAcquirer(
            transport,
            workers=1,
            timeout_seconds=5.0,
            leases=leases,
            clock=lambda: 100.0,
        )

        envelope = acquirer.collect_authoritative((miner,), self.epoch())[miner.key]
        acquirer.close()
        leases.release(lease)

        self.assertEqual((Quality.ERROR, "scheduled_overlap"), (
            envelope.quality,
            envelope.reason_code,
        ))
        self.assertEqual([], transport.calls)

    def test_deadline_returns_complete_epoch_while_slow_lease_stays_owned(self) -> None:
        slow_release = threading.Event()
        slow_started = threading.Event()

        def blocked() -> TransportOutcome:
            slow_started.set()
            slow_release.wait(2.0)
            return outcome(summary_payload(), completed=time.monotonic())

        now = time.monotonic()
        epoch = AcquisitionEpoch(8, now, now + 0.05, 2_000.0)
        miners = self.miners[:2]
        transport = ScriptedTransport({
            ("miner-a", "summary"): blocked,
            ("miner-b", "summary"): outcome(summary_payload(), completed=now + 0.01),
            ("miner-b", "stats"): outcome(stats_payload(), completed=now + 0.02),
        })
        leases = InFlightRegistry()
        acquirer = BoundedAcquirer(
            transport,
            workers=2,
            timeout_seconds=5.0,
            leases=leases,
        )

        started = time.monotonic()
        envelopes = acquirer.collect_authoritative(miners, epoch)
        duration = time.monotonic() - started

        self.assertTrue(slow_started.is_set())
        self.assertLess(duration, 0.5)
        self.assertEqual(Quality.LATE, envelopes["miner-a"].quality)
        self.assertEqual(Quality.VALID, envelopes["miner-b"].quality)
        self.assertTrue(leases.is_owned("miner-a"))
        second = acquirer.collect_authoritative((miners[0],), AcquisitionEpoch(9, now + 0.06, now + 1.0, 2_001.0))
        self.assertEqual("scheduled_overlap", second["miner-a"].reason_code)
        slow_release.set()
        acquirer.close()
        self.assertFalse(leases.is_owned("miner-a"))

    def test_duplicate_miner_keys_are_rejected_before_io(self) -> None:
        transport = ScriptedTransport({})
        acquirer = BoundedAcquirer(
            transport, workers=1, timeout_seconds=5.0, clock=lambda: 100.0
        )
        with self.assertRaises(ValueError):
            acquirer.collect_authoritative((self.miners[0], self.miners[0]), self.epoch())
        acquirer.close()
        self.assertEqual([], transport.calls)

    def test_fleet_transport_failure_is_distinct_and_health_is_bounded(self) -> None:
        transport = ScriptedTransport({
            (miner.key, "summary"): outcome(status=TransportStatus.ERROR)
            for miner in self.miners
        })
        health = PollHealth(latency_window_size=3)
        acquirer = BoundedAcquirer(
            transport,
            workers=2,
            timeout_seconds=5.0,
            poll_health=health,
            clock=lambda: 100.0,
        )

        envelopes = acquirer.collect_authoritative(self.miners, self.epoch())
        acquirer.close()

        self.assertTrue(all(item.reason_code == "transport_error" for item in envelopes.values()))
        snapshot = health.snapshot()
        self.assertEqual("fleet_transport_failure", snapshot.fleet_reason_code)
        self.assertEqual(4, snapshot.last_epoch_completed_count)
        self.assertLessEqual(len(snapshot.latency_window), 3)

    def test_diagnostic_budget_is_summary_only_and_has_no_authority(self) -> None:
        miners = self.miners[:2]
        transport = ScriptedTransport({
            (miner.key, "summary"): outcome(summary_payload())
            for miner in miners
        })
        acquirer = BoundedAcquirer(
            transport, workers=2, timeout_seconds=5.0, clock=lambda: 100.0
        )

        envelopes = acquirer.collect_diagnostic(
            miners,
            diagnostic_id=3,
            observed_ts=1_000.0,
            deadline_monotonic=112.0,
        )
        acquirer.close()

        self.assertTrue(all(item.authority is Authority.DIAGNOSTIC for item in envelopes.values()))
        self.assertEqual(2, sum(item.summary_requests for item in envelopes.values()))
        self.assertEqual(0, sum(item.stats_requests for item in envelopes.values()))
        self.assertTrue(all(call[1] == "summary" for call in transport.calls))
        applied: list[str] = []
        self.assertEqual(0, dispatch_authoritative(envelopes.values(), applied.append))
        self.assertEqual([], applied)

    def test_stable_summary_failure_vocabulary_is_complete(self) -> None:
        cases = (
            (outcome(status=TransportStatus.EMPTY), Quality.INVALID, "empty_payload"),
            (outcome(status=TransportStatus.INVALID_JSON), Quality.INVALID, "invalid_json"),
            (outcome({}), Quality.INVALID, "summary_missing"),
            (outcome(status=TransportStatus.TIMEOUT), Quality.TIMEOUT, "transport_timeout"),
            (outcome(status=TransportStatus.ERROR), Quality.ERROR, "transport_error"),
        )
        miner = self.miners[0]
        for transport_result, quality, reason in cases:
            with self.subTest(reason=reason):
                transport = ScriptedTransport({(miner.key, "summary"): transport_result})
                acquirer = BoundedAcquirer(
                    transport, workers=1, timeout_seconds=5.0, clock=lambda: 100.0
                )
                envelope = acquirer.collect_authoritative((miner,), self.epoch())[miner.key]
                acquirer.close()
                self.assertEqual((quality, reason), (envelope.quality, envelope.reason_code))
                self.assertEqual(1, envelope.summary_requests)
                self.assertEqual(0, envelope.stats_requests)

    def test_sanitized_fixture_contains_all_red_contract_scenarios(self) -> None:
        fixture = json.loads(
            Path("specs/022-adaptive-acquisition/fixtures/acquisition-contract.json")
            .read_text(encoding="utf-8")
        )
        scenario_ids = {item["id"] for item in fixture["scenarios"]}
        self.assertEqual(
            {
                "all_valid_out_of_order",
                "one_timeout_peers_complete",
                "summary_valid_stats_missing",
                "invalid_rate",
                "late_result",
                "scheduled_overlap",
                "resume_skips_missed_epochs",
                "diagnostic_recovery_no_authority",
                "disabled_path",
            },
            scenario_ids,
        )


class AuthorityFirewallTests(unittest.TestCase):
    def test_diagnostic_and_late_envelopes_never_reach_authoritative_consumer(self) -> None:
        base = dict(
            miner_key="miner-a",
            epoch_id=1,
            observed_ts=1_000.0,
            completed_monotonic=100.0,
            latency_ms=5.0,
            responded=True,
            rate_ths=95.0,
            elapsed_seconds=600,
            active_boards=3,
            summary_entry=None,
            stats_response=None,
            summary_requests=1,
            stats_requests=0,
        )
        valid = MinerSampleEnvelope(
            **base,
            authority=Authority.AUTHORITATIVE,
            quality=Quality.VALID,
            reason_code="ok",
        )
        diagnostic = MinerSampleEnvelope(
            **base,
            authority=Authority.DIAGNOSTIC,
            quality=Quality.VALID,
            reason_code="ok",
        )
        late = MinerSampleEnvelope(
            **base,
            authority=Authority.AUTHORITATIVE,
            quality=Quality.LATE,
            reason_code="epoch_deadline_exceeded",
        )
        applied: list[str] = []

        count = dispatch_authoritative(
            (diagnostic, late, valid),
            lambda item: applied.append(item.miner_key),
        )

        self.assertEqual(1, count)
        self.assertEqual(["miner-a"], applied)


if __name__ == "__main__":
    unittest.main()
