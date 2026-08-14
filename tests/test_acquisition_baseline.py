import json
import tempfile
import unittest
from pathlib import Path

from app.acquisition import MinerEndpoint, TransportOutcome, TransportStatus
from tools.acquisition_baseline import (
    build_sanitized_endpoints,
    nearest_rank_percentile,
    run_sequential_baseline,
    write_json_atomic,
)


class FakeTransport:
    def __init__(self, outcomes: dict[tuple[str, str], TransportOutcome]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, str, float]] = []

    def __call__(
        self,
        endpoint: MinerEndpoint,
        command: str,
        timeout_seconds: float,
    ) -> TransportOutcome:
        self.calls.append((endpoint.key, command, timeout_seconds))
        return self.outcomes[(endpoint.key, command)]


def success(payload: dict, latency_ms: float) -> TransportOutcome:
    return TransportOutcome(
        status=TransportStatus.SUCCESS,
        payload=payload,
        completed_monotonic=1.0,
        latency_ms=latency_ms,
    )


class AcquisitionBaselineTests(unittest.TestCase):
    def test_endpoints_are_sanitized_and_invalid_entries_are_ignored(self) -> None:
        endpoints = build_sanitized_endpoints({
            "miners": [
                {"name": "secret-name", "host": "192.0.2.1", "port": 4028},
                {"name": "broken", "host": "", "port": 4028},
            ]
        })

        self.assertEqual(1, len(endpoints))
        self.assertEqual("miner-1", endpoints[0].key)
        self.assertEqual("192.0.2.1", endpoints[0].host)

    def test_current_sequential_order_and_conditional_stats_budget(self) -> None:
        endpoints = (
            MinerEndpoint("miner-1", "example.invalid", 4028),
            MinerEndpoint("miner-2", "example.invalid", 4028),
        )
        transport = FakeTransport({
            ("miner-1", "summary"): success(
                {"SUMMARY": [{"GHS 5s": 95_000}]}, 10.0
            ),
            ("miner-1", "stats"): success({"STATS": [{}]}, 20.0),
            ("miner-2", "summary"): TransportOutcome(
                status=TransportStatus.TIMEOUT,
                completed_monotonic=1.0,
                latency_ms=5_000.0,
            ),
        })
        clock_values = iter((100.0, 105.03))

        report = run_sequential_baseline(
            endpoints,
            transport=transport,
            samples=1,
            timeout_seconds=5.0,
            poll_seconds=30.0,
            pause_seconds=0.0,
            clock=lambda: next(clock_values),
            sleep=lambda _seconds: None,
            captured_ts=1_000.0,
        )

        self.assertEqual(
            [
                ("miner-1", "summary", 5.0),
                ("miner-1", "stats", 5.0),
                ("miner-2", "summary", 5.0),
            ],
            transport.calls,
        )
        self.assertEqual(2, report["request_totals"]["summary"])
        self.assertEqual(1, report["request_totals"]["stats"])
        self.assertEqual("partial", report["capture_status"])
        self.assertEqual(5_030.0, report["cycle_latency_ms"]["p50"])
        encoded = json.dumps(report)
        self.assertNotIn("example.invalid", encoded)
        self.assertNotIn("192.", encoded)

    def test_all_failed_summaries_mark_capture_failed(self) -> None:
        endpoint = MinerEndpoint("miner-1", "example.invalid", 4028)
        transport = FakeTransport({
            (endpoint.key, "summary"): TransportOutcome(
                status=TransportStatus.ERROR,
                completed_monotonic=1.0,
                latency_ms=1.0,
            )
        })
        clock_values = iter((100.0, 100.001))

        report = run_sequential_baseline(
            (endpoint,),
            transport=transport,
            samples=1,
            timeout_seconds=5.0,
            poll_seconds=30.0,
            pause_seconds=0.0,
            clock=lambda: next(clock_values),
            sleep=lambda _seconds: None,
            captured_ts=1_000.0,
        )

        self.assertEqual("failed", report["capture_status"])

    def test_nearest_rank_percentiles_and_atomic_replace(self) -> None:
        self.assertEqual(1.0, nearest_rank_percentile([1.0, 2.0, 3.0, 4.0], 0.01))
        self.assertEqual(2.0, nearest_rank_percentile([1.0, 2.0, 3.0, 4.0], 0.50))
        self.assertEqual(4.0, nearest_rank_percentile([1.0, 2.0, 3.0, 4.0], 0.95))
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "baseline.json"
            path.write_text("stale", encoding="utf-8")
            write_json_atomic(path, {"schema_version": 1})
            self.assertEqual(
                {"schema_version": 1},
                json.loads(path.read_text(encoding="utf-8")),
            )
            self.assertEqual([], list(path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
