import unittest
from pathlib import Path

from tools.observe_liveness import (
    evaluate,
    parse_service_query,
    parse_timestamp,
    parse_watchdog_lines,
    summarize_watchdog,
)


class LivenessObservationTests(unittest.TestCase):
    def test_installer_is_hidden_bounded_and_fails_closed(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "tools"
            / "install_liveness_observation_tasks.ps1"
        ).read_text(encoding="utf-8-sig")
        for required in (
            "pythonw.exe",
            'UserId "SYSTEM"',
            "ServiceAccount",
            "StartWhenAvailable",
            "MultipleInstances IgnoreNew",
            "ExecutionTimeLimit",
            "-ErrorAction Stop",
        ):
            self.assertIn(required, script)
        for forbidden in (
            "run_hashcore",
            "Restart-Service",
            "Stop-Service",
            "taskkill",
            "send_telegram",
        ):
            self.assertNotIn(forbidden, script)

    def test_service_query_accepts_english_and_spanish_labels(self) -> None:
        self.assertEqual((True, 42), parse_service_query("STATE : 4 RUNNING\nPID : 42"))
        self.assertEqual((True, 77), parse_service_query("ESTADO : 4 RUNNING\nPID : 77"))
        self.assertEqual((False, 0), parse_service_query("ESTADO : 1 STOPPED\nPID : 0"))

    def test_watchdog_summary_is_bounded_to_observation_start(self) -> None:
        lines = [
            "[2026-08-13 17:22:53] WATCHDOG assessment healthy=false suppressed=true reasons=service_stopped service=stopped service_pid=0 tick_age=61 poller_age=99 sender_age=64 action=none",
            "[2026-08-13 17:23:53] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=35836 tick_age=7 poller_age=11 sender_age=9 action=none",
            "[2026-08-13 17:24:53] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=35836 tick_age=30 poller_age=72 sender_age=33 action=none",
        ]
        samples = parse_watchdog_lines(
            lines, since_ts=parse_timestamp("2026-08-13T17:23:14-03:00")
        )
        summary = summarize_watchdog(samples)
        self.assertEqual(2, summary["sample_count"])
        self.assertEqual(0, summary["unhealthy_count"])
        self.assertEqual(30, summary["tick_age"]["max"])
        self.assertEqual(72, summary["poller_age"]["max"])
        self.assertEqual([35836], summary["service_pids"])
        self.assertEqual(1.0, summary["cadence_coverage"])

    def test_evaluate_rejects_early_stage_and_actions(self) -> None:
        report = self._healthy_report()
        report["observation"]["elapsed_seconds"] = 3600
        report["observation"]["required_seconds"] = 86_400
        report["database"]["action_decisions"] = 1
        self.assertEqual(
            ["observation_window_incomplete", "auto_reboot_decision_observed"],
            evaluate(report),
        )

    def test_evaluate_accepts_complete_healthy_observation(self) -> None:
        self.assertEqual([], evaluate(self._healthy_report()))

    def test_evaluate_rejects_stale_persistence_and_collector_failure(self) -> None:
        report = self._healthy_report()
        report["database"]["latest_sample_age_seconds"] = 601
        report["database"]["latest_collector"] = {"status": "partial", "failed": 1}
        self.assertEqual(
            ["telemetry_samples_stale", "collector_latest_run_failed"],
            evaluate(report),
        )

    def test_evaluate_rejects_clock_skew_stale_tail_and_pid_change(self) -> None:
        report = self._healthy_report()
        report["heartbeat"]["tick_age_seconds"] = -6
        report["watchdog"]["tail_age_seconds"] = 121
        report["watchdog"]["service_pids"] = [11111, 35836]
        self.assertEqual(
            [
                "tick_clock_skew",
                "watchdog_tail_stale",
                "watchdog_service_pid_changed",
            ],
            evaluate(report),
        )

    @staticmethod
    def _healthy_report() -> dict:
        return {
            "observation": {"elapsed_seconds": 86_400, "required_seconds": 86_400},
            "service": {"running": True, "pid": 35836},
            "thresholds": {
                "tick_stale_seconds": 120,
                "worker_stale_seconds": 120,
                "collector_stale_seconds": 7200,
                "clock_skew_tolerance_seconds": 5,
                "telemetry_sample_stale_seconds": 600,
            },
            "heartbeat": {
                "schema_version": 1,
                "pid": 35788,
                "tick_age_seconds": 30,
                "poller_age_seconds": 60,
                "sender_age_seconds": 30,
                "collector_age_seconds": 600,
            },
            "watchdog": {
                "sample_count": 1400,
                "unhealthy_count": 0,
                "reason_count": 0,
                "action_count": 0,
                "cadence_coverage": 0.99,
                "head_delay_seconds": 39,
                "tail_age_seconds": 30,
                "service_pids": [35836],
            },
            "watchdog_state": {"is_open": False},
            "database": {
                "action_decisions": 0,
                "automatic_action_events": 0,
                "latest_sample_age_seconds": 30,
                "latest_collector": {"status": "ok", "failed": 0},
            },
        }


if __name__ == "__main__":
    unittest.main()
