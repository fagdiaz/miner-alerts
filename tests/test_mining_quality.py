import inspect
import json
import tempfile
import unittest
from pathlib import Path

import app.miner_monitor as monitor
from app.event_store import EventStore
from app.mining_quality import (
    STATUS_CRITICAL,
    STATUS_LEARNING,
    STATUS_STABLE,
    STATUS_WATCH,
    analyze_mining_quality,
    normalize_mining_quality,
    render_mining_quality,
)


def sample(
    observed_ts: float,
    *,
    elapsed_seconds: object = 10_000,
    accepted: object = 1_000,
    rejected: object = 5,
    stale: object = 2,
    hw_errors: object = 10,
    chain_fault_count: object = 0,
    chains_not_mining_count: object = 0,
    chains_transitioning_count: object = 0,
) -> dict[str, object]:
    return {
        "observed_ts": observed_ts,
        "miner_key": "m23",
        "miner_name": "23",
        "state": "OK",
        "responded": 1,
        "rate_ths": 100.0,
        "threshold_ths": 60.0,
        "elapsed_seconds": elapsed_seconds,
        "accepted_shares_total": accepted,
        "rejected_shares_total": rejected,
        "stale_shares_total": stale,
        "hw_errors_total": hw_errors,
        "chain_fault_count": chain_fault_count,
        "chains_not_mining_count": chains_not_mining_count,
        "chains_transitioning_count": chains_transitioning_count,
    }


class MiningQualityTests(unittest.TestCase):
    def test_normalizes_counters_and_chain_evidence_without_raw_payload(self) -> None:
        summary = {
            "Accepted": "1000",
            "Rejected": 12,
            "Stale": 3.0,
            "Elapsed": 5000,
        }
        stats = {
            "STATS": [
                {"Type": "Antminer"},
                {
                    "chain_state1": "mining",
                    "chain_state2": "autotune",
                    "chain_state3": "stopped",
                    "chain_fault1": "",
                    "chain_fault2": "none",
                    "chain_fault3": "crc_error",
                },
            ]
        }

        telemetry = normalize_mining_quality(summary, stats, expected_boards=3)

        self.assertEqual(1000, telemetry.accepted_shares_total)
        self.assertEqual(12, telemetry.rejected_shares_total)
        self.assertEqual(3, telemetry.stale_shares_total)
        self.assertEqual(1, telemetry.chain_fault_count)
        self.assertEqual(1, telemetry.chains_not_mining_count)
        self.assertEqual(1, telemetry.chains_transitioning_count)
        self.assertIn("chain_fault_present", telemetry.quality_flags)
        self.assertIn("firmware_transition", telemetry.quality_flags)
        serialized = telemetry.as_dict()
        self.assertNotIn("raw", serialized)
        self.assertNotIn("chain_faults", serialized)

    def test_malformed_values_are_unknown_not_faults(self) -> None:
        telemetry = normalize_mining_quality(
            {"Accepted": -1, "Rejected": "bad", "Stale": float("nan")},
            {"STATS": [{"chain_state1": "", "chain_fault1": "0"}]},
            expected_boards=3,
        )

        self.assertIsNone(telemetry.accepted_shares_total)
        self.assertIsNone(telemetry.rejected_shares_total)
        self.assertIsNone(telemetry.stale_shares_total)
        self.assertEqual(0, telemetry.chain_fault_count)
        self.assertEqual(0, telemetry.chains_not_mining_count)
        self.assertIn("share_counters_missing", telemetry.quality_flags)

    def test_stable_interval_uses_deltas_not_lifetime_percentages(self) -> None:
        rows = [
            sample(2_000, elapsed_seconds=10_300, accepted=1_300, rejected=5, stale=2),
            sample(1_700, elapsed_seconds=10_000, accepted=1_000, rejected=5, stale=2),
            sample(1_400, elapsed_seconds=9_700, accepted=700, rejected=5, stale=2),
            sample(1_100, elapsed_seconds=9_400, accepted=400, rejected=5, stale=2),
        ]

        assessment = analyze_mining_quality(rows)

        self.assertEqual(STATUS_STABLE, assessment.status)
        self.assertEqual(300, assessment.delta.accepted)
        self.assertEqual(0, assessment.delta.rejected)
        self.assertEqual(0, assessment.delta.stale)
        self.assertEqual(0.0, assessment.delta.rejected_percent)
        self.assertEqual(3, assessment.comparable_intervals)

    def test_rejected_and_stale_interval_is_watch(self) -> None:
        latest = sample(
            2_000,
            elapsed_seconds=10_300,
            accepted=1_090,
            rejected=15,
            stale=7,
            hw_errors=25,
        )
        previous = sample(
            1_700,
            elapsed_seconds=10_000,
            accepted=1_000,
            rejected=5,
            stale=2,
            hw_errors=10,
        )

        assessment = analyze_mining_quality(
            [latest, previous],
            min_intervals=1,
            reject_warning_percent=5.0,
            stale_warning_percent=3.0,
            hw_error_delta_warning=10,
        )

        self.assertEqual(STATUS_WATCH, assessment.status)
        self.assertIn("rejected_share_rate", assessment.reason_codes)
        self.assertIn("stale_share_rate", assessment.reason_codes)
        self.assertIn("hardware_error_growth", assessment.reason_codes)
        self.assertAlmostEqual(9.5238, assessment.delta.rejected_percent)
        self.assertAlmostEqual(4.7619, assessment.delta.stale_percent)

    def test_counter_or_uptime_reset_is_learning_without_negative_delta(self) -> None:
        assessment = analyze_mining_quality(
            [
                sample(2_000, elapsed_seconds=120, accepted=10, rejected=0, stale=0),
                sample(1_700, elapsed_seconds=50_000, accepted=8_000, rejected=20, stale=8),
            ],
            min_intervals=1,
        )

        self.assertEqual(STATUS_LEARNING, assessment.status)
        self.assertTrue(assessment.delta.counter_reset)
        self.assertIsNone(assessment.delta.accepted)
        self.assertIn("counter_reset", assessment.reason_codes)

    def test_current_chain_fault_precedes_share_quality(self) -> None:
        assessment = analyze_mining_quality(
            [
                sample(2_000, chain_fault_count=1, chains_not_mining_count=1),
                sample(1_700, elapsed_seconds=9_700, accepted=900),
            ],
            min_intervals=1,
        )

        self.assertEqual(STATUS_CRITICAL, assessment.status)
        self.assertIn("chain_fault", assessment.reason_codes)
        self.assertIn("chain_not_mining", assessment.reason_codes)
        self.assertNotIn("rejected_share_rate", assessment.reason_codes)

    def test_firmware_transition_is_watch_and_advises_observation(self) -> None:
        assessment = analyze_mining_quality(
            [
                sample(2_000, chains_transitioning_count=1),
                sample(1_700, elapsed_seconds=9_700, accepted=900),
            ],
            min_intervals=1,
        )
        rendered = render_mining_quality("23", assessment)

        self.assertEqual(STATUS_WATCH, assessment.status)
        self.assertIn("firmware_transition", assessment.reason_codes)
        self.assertIn("observar", rendered.lower())
        self.assertLessEqual(len(rendered.splitlines()), 8)

    def test_analyzer_is_pure_and_has_no_action_or_io_dependency(self) -> None:
        source = inspect.getsource(analyze_mining_quality)
        for forbidden in (
            "socket",
            "requests",
            "subprocess",
            "run_hashcore_cli",
            "read_summary",
            "read_stats",
            "open(",
        ):
            self.assertNotIn(forbidden, source)

    def test_quality_command_is_registered_and_read_only(self) -> None:
        item = {
            "message": {
                "text": "/quality@MinerAlertsBot 23",
                "entities": [{"type": "bot_command", "offset": 0, "length": 23}],
            }
        }
        _, _, cmd_name, args, _, _ = monitor._parse_message_command(item)
        names = {entry["name"] for entry in monitor._COMMANDS}

        self.assertEqual("quality", cmd_name)
        self.assertEqual(["23"], args)
        self.assertIn("quality", names)
        self.assertIn("/quality", monitor.render_help_index())

        source = inspect.getsource(monitor.telegram_polling_worker)
        quality_branch = source.split('elif cmd_name == "quality":', 1)[1].split(
            'elif cmd_name == "health":', 1
        )[0]
        helper_source = inspect.getsource(monitor.build_mining_quality_text)
        self.assertIn("build_mining_quality_text", quality_branch)
        self.assertIn("is_command=True", quality_branch)
        self.assertIn('dbg_cmd="quality"', quality_branch)
        self.assertIn("event_store.list_samples", helper_source)
        for forbidden in (
            "read_summary",
            "read_stats",
            "read_pools",
            "read_version",
            "run_hashcore_cli",
        ):
            self.assertNotIn(forbidden, quality_branch)
            self.assertNotIn(forbidden, helper_source)

    def test_quality_report_reads_persisted_samples_and_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(Path(temp_dir) / "quality.db")
            try:
                for index in range(4):
                    store.record_sample(
                        observed_ts=2_000.0 - index * 300,
                        miner_key="S19JPRO-23|h23:4028",
                        miner_name="23",
                        host="h23",
                        state="OK",
                        responded=True,
                        rate_ths=100.0,
                        threshold_ths=60.0,
                        active_boards=3,
                        expected_boards=3,
                        elapsed_seconds=10_000 - index * 300,
                        telemetry={
                            "accepted_shares_total": 1_300 - index * 300,
                            "rejected_shares_total": 5,
                            "stale_shares_total": 2,
                            "chain_fault_count": 0,
                            "chains_not_mining_count": 0,
                            "chains_transitioning_count": 0,
                        },
                    )
                miners = [{"name": "S19JPRO-23", "host": "h23", "port": 4028}]
                rendered = monitor.build_mining_quality_text(
                    store,
                    miners,
                    "23",
                    now_ts=2_010.0,
                    min_intervals=3,
                )
                unknown = monitor.build_mining_quality_text(
                    store, miners, "99", now_ts=2_010.0
                )
            finally:
                store.close()

        self.assertIn("QUALITY (historial local)", rendered)
        self.assertIn("23  STABLE", rendered)
        self.assertEqual("Miner no encontrado.", unknown)

    def test_production_example_has_bounded_quality_defaults(self) -> None:
        config = json.loads(Path("app/config.example.json").read_text(encoding="utf-8"))

        self.assertEqual(3, config["quality_min_intervals"])
        self.assertEqual(1.0, config["quality_reject_warning_percent"])
        self.assertEqual(1.0, config["quality_stale_warning_percent"])
        self.assertEqual(50, config["quality_hw_error_delta_warning"])
        self.assertEqual(900, config["quality_no_share_warning_seconds"])


if __name__ == "__main__":
    unittest.main()
