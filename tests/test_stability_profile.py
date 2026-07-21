import inspect
import json
import tempfile
import unittest
from pathlib import Path

import app.miner_monitor as monitor
from app.event_store import EventStore
from app.stability_profile import (
    STATUS_CRITICAL,
    STATUS_LEARNING,
    STATUS_STABLE,
    STATUS_WATCH,
    analyze_stability,
    render_stability_assessment,
)


def sample(
    observed_ts: float,
    *,
    state: str = "OK",
    responded: bool = True,
    rate_ths: object = 100.0,
    threshold_ths: float = 60.0,
    active_boards: object = 3,
    expected_boards: int = 3,
    max_temp_c: object = 75.0,
    chain_voltage_mv_avg: object = 12_800.0,
    chain_power_w_total: object = 3_000.0,
    frequency_mhz_avg: object = 500.0,
) -> dict[str, object]:
    return {
        "observed_ts": observed_ts,
        "miner_key": "m23",
        "miner_name": "23",
        "state": state,
        "responded": 1 if responded else 0,
        "rate_ths": rate_ths,
        "threshold_ths": threshold_ths,
        "active_boards": active_boards,
        "expected_boards": expected_boards,
        "max_temp_c": max_temp_c,
        "chain_voltage_mv_avg": chain_voltage_mv_avg,
        "chain_power_w_total": chain_power_w_total,
        "frequency_mhz_avg": frequency_mhz_avg,
    }


def stable_history(*, latest: dict[str, object] | None = None) -> list[dict[str, object]]:
    rows = [
        sample(
            1_900.0 - index * 60,
            rate_ths=99.5 + (index % 3) * 0.5,
            max_temp_c=74.0 + (index % 3),
            chain_voltage_mv_avg=12_790.0 + (index % 3) * 10.0,
            chain_power_w_total=2_980.0 + (index % 3) * 20.0,
            frequency_mhz_avg=498.0 + (index % 3) * 2.0,
        )
        for index in range(12)
    ]
    return [latest or sample(2_000.0), *rows]


class StabilityProfileTests(unittest.TestCase):
    def test_stable_history_builds_robust_bands_and_excludes_latest(self) -> None:
        assessment = analyze_stability(stable_history(), now_ts=2_010.0)

        self.assertEqual(STATUS_STABLE, assessment.status)
        self.assertEqual(12, assessment.sample_count)
        self.assertEqual(1.0, assessment.confidence)
        self.assertEqual(12, assessment.bands["rate_ths"].sample_count)
        self.assertAlmostEqual(100.0, assessment.bands["rate_ths"].median)
        self.assertEqual((), assessment.reasons)

    def test_insufficient_clean_history_is_learning_not_stable(self) -> None:
        rows = [sample(2_000.0), *[sample(1_900.0 - index) for index in range(5)]]

        assessment = analyze_stability(rows, now_ts=2_010.0, min_samples=12)

        self.assertEqual(STATUS_LEARNING, assessment.status)
        self.assertEqual(5, assessment.sample_count)
        self.assertAlmostEqual(5 / 12, assessment.confidence, places=3)
        self.assertIn("baseline_learning", assessment.reason_codes)

    def test_hard_faults_take_precedence_over_statistical_drift(self) -> None:
        latest = sample(
            2_000.0,
            state="LOW",
            rate_ths=50.0,
            active_boards=2,
            max_temp_c=87.0,
            chain_voltage_mv_avg=11_000.0,
        )

        assessment = analyze_stability(stable_history(latest=latest), now_ts=2_010.0)

        self.assertEqual(STATUS_CRITICAL, assessment.status)
        self.assertIn("state_low", assessment.reason_codes)
        self.assertIn("rate_below_threshold", assessment.reason_codes)
        self.assertIn("board_missing", assessment.reason_codes)
        self.assertIn("high_temperature", assessment.reason_codes)
        self.assertNotIn("chain_voltage_drift", assessment.reason_codes)

    def test_stale_or_invalid_current_signal_is_critical(self) -> None:
        stale = analyze_stability(stable_history(), now_ts=3_000.0, stale_after_seconds=300)
        invalid = analyze_stability(
            stable_history(latest=sample(2_000.0, responded=False, rate_ths=None)),
            now_ts=2_010.0,
        )

        self.assertEqual(STATUS_CRITICAL, stale.status)
        self.assertIn("stale_sample", stale.reason_codes)
        self.assertEqual(STATUS_CRITICAL, invalid.status)
        self.assertIn("no_response", invalid.reason_codes)

    def test_recovered_signal_during_state_hysteresis_is_watch_not_critical(self) -> None:
        latest = sample(2_000.0, state="LOW", rate_ths=100.0)

        assessment = analyze_stability(stable_history(latest=latest), now_ts=2_010.0)

        self.assertEqual(STATUS_WATCH, assessment.status)
        self.assertIn("state_recovery_hysteresis", assessment.reason_codes)
        self.assertNotIn("state_low", assessment.reason_codes)

    def test_soft_drift_is_watch_and_voltage_is_not_called_ac_input(self) -> None:
        latest = sample(
            2_000.0,
            rate_ths=90.0,
            max_temp_c=82.0,
            chain_voltage_mv_avg=12_000.0,
            chain_power_w_total=3_500.0,
            frequency_mhz_avg=550.0,
        )

        assessment = analyze_stability(stable_history(latest=latest), now_ts=2_010.0)
        rendered = render_stability_assessment("23", assessment)

        self.assertEqual(STATUS_WATCH, assessment.status)
        self.assertIn("rate_below_baseline", assessment.reason_codes)
        self.assertIn("temperature_above_baseline", assessment.reason_codes)
        self.assertIn("chain_voltage_drift", assessment.reason_codes)
        self.assertIn("power_drift", assessment.reason_codes)
        self.assertIn("frequency_drift", assessment.reason_codes)
        self.assertIn("no es voltaje AC", rendered)

    def test_malformed_optional_values_are_ignored_without_crash(self) -> None:
        latest = sample(
            2_000.0,
            max_temp_c="bad",
            chain_voltage_mv_avg=float("nan"),
            chain_power_w_total=None,
            frequency_mhz_avg=True,
        )
        rows = stable_history(latest=latest)
        rows[3]["chain_power_w_total"] = "not-a-number"

        assessment = analyze_stability(rows, now_ts=2_010.0)

        self.assertEqual(STATUS_STABLE, assessment.status)
        self.assertNotIn("chain_voltage_drift", assessment.reason_codes)

    def test_render_is_bounded_and_exposes_learning_progress(self) -> None:
        rows = [sample(2_000.0), sample(1_900.0)]
        assessment = analyze_stability(rows, now_ts=2_010.0, min_samples=12)

        rendered = render_stability_assessment("23", assessment, max_reasons=3)

        self.assertIn("23  LEARNING 1/12", rendered)
        self.assertLessEqual(len(rendered.splitlines()), 8)

    def test_analyzer_source_has_no_io_action_or_monitor_dependency(self) -> None:
        source = inspect.getsource(analyze_stability)
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

    def test_health_command_contract_is_registered_parsed_and_read_only(self) -> None:
        item = {
            "message": {
                "text": "/health@MinerAlertsBot 23",
                "entities": [{"type": "bot_command", "offset": 0, "length": 22}],
            }
        }
        _, _, cmd_name, args, _, _ = monitor._parse_message_command(item)
        names = {entry["name"] for entry in monitor._COMMANDS}

        self.assertEqual("health", cmd_name)
        self.assertEqual(["23"], args)
        self.assertIn("health", names)
        self.assertIn("/health", monitor.render_help_index())

        source = inspect.getsource(monitor.telegram_polling_worker)
        health_branch = source.split('elif cmd_name == "health":', 1)[1].split(
            'elif cmd_name == "status":', 1
        )[0]
        self.assertIn("build_stability_health_text", health_branch)
        self.assertIn("is_command=True", health_branch)
        self.assertIn('dbg_cmd="health"', health_branch)
        helper_source = inspect.getsource(monitor.build_stability_health_text)
        self.assertIn("event_store.list_samples", helper_source)
        self.assertIn("analyze_stability", helper_source)
        for forbidden in (
            "read_summary",
            "read_stats",
            "read_pools",
            "read_version",
            "run_hashcore_cli",
        ):
            self.assertNotIn(forbidden, health_branch)
            self.assertNotIn(forbidden, helper_source)

    def test_health_report_uses_persisted_samples_and_handles_unknown_miner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventStore(Path(temp_dir) / "health.db")
            try:
                for index in range(13):
                    store.record_sample(
                        observed_ts=2_000.0 - index * 60,
                        miner_key="S19JPRO-23|h23:4028",
                        miner_name="23",
                        host="h23",
                        state="OK",
                        responded=True,
                        rate_ths=100.0,
                        threshold_ths=60.0,
                        active_boards=3,
                        expected_boards=3,
                        elapsed_seconds=50_000,
                        telemetry={"max_temp_c": 75.0},
                    )
                miners = [{"name": "S19JPRO-23", "host": "h23", "port": 4028}]
                rendered = monitor.build_stability_health_text(
                    store,
                    miners,
                    "23",
                    now_ts=2_010.0,
                    window_hours=168.0,
                    min_samples=12,
                    stale_after_seconds=900.0,
                )
                unknown = monitor.build_stability_health_text(
                    store,
                    miners,
                    "99",
                    now_ts=2_010.0,
                )
                bounded = monitor.build_stability_health_text(
                    store,
                    [
                        {"name": f"S19JPRO-{index}", "host": f"h{index}", "port": 4028}
                        for index in range(1, 13)
                    ],
                    "all",
                    now_ts=2_010.0,
                )
            finally:
                store.close()

        self.assertIn("HEALTH (historial local)", rendered)
        self.assertIn("23  STABLE", rendered)
        self.assertEqual("Miner no encontrado.", unknown)
        self.assertIn("2 mineros omitidos", bounded)

    def test_production_example_has_bounded_advisor_defaults(self) -> None:
        config = json.loads(
            Path("app/config.example.json").read_text(encoding="utf-8")
        )

        self.assertEqual(168, config["stability_window_hours"])
        self.assertEqual(12, config["stability_min_samples"])
        self.assertEqual(900, config["stability_stale_seconds"])


if __name__ == "__main__":
    unittest.main()
