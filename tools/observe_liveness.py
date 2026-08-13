"""Read-only D+0/D+1/D+3 observation gate for monitor liveness."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE_SECONDS = {"d0": 0, "d1": 86_400, "d3": 259_200}
ASSESSMENT_RE = re.compile(
    r"^\[(?P<timestamp>[^]]+)] WATCHDOG assessment "
    r"healthy=(?P<healthy>\w+) suppressed=(?P<suppressed>\w+) "
    r"reasons=(?P<reasons>\S+) service=(?P<service>\S+) "
    r"service_pid=(?P<service_pid>\d+) tick_age=(?P<tick_age>\d+) "
    r"poller_age=(?P<poller_age>\d+) sender_age=(?P<sender_age>\d+) "
    r"action=(?P<action>\S+)$"
)


@dataclass(frozen=True)
class WatchdogSample:
    timestamp: float
    healthy: bool
    suppressed: bool
    reasons: str
    service: str
    service_pid: int
    tick_age: int
    poller_age: int
    sender_age: int
    action: str


def parse_timestamp(value: str) -> float:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.timestamp()


def parse_service_query(output: str) -> tuple[bool, int | None]:
    running = bool(re.search(r"(?:STATE|ESTADO)\s*:\s*4\s+RUNNING", output, re.I))
    pid_match = re.search(r"\bPID\s*:\s*(\d+)", output, re.I)
    return running, int(pid_match.group(1)) if pid_match else None


def parse_watchdog_lines(lines: Iterable[str], *, since_ts: float) -> list[WatchdogSample]:
    samples: list[WatchdogSample] = []
    for line in lines:
        match = ASSESSMENT_RE.match(line.strip())
        if not match:
            continue
        values = match.groupdict()
        timestamp = parse_timestamp(values["timestamp"])
        if timestamp < since_ts:
            continue
        samples.append(
            WatchdogSample(
                timestamp=timestamp,
                healthy=values["healthy"] == "true",
                suppressed=values["suppressed"] == "true",
                reasons=values["reasons"],
                service=values["service"],
                service_pid=int(values["service_pid"]),
                tick_age=int(values["tick_age"]),
                poller_age=int(values["poller_age"]),
                sender_age=int(values["sender_age"]),
                action=values["action"],
            )
        )
    return samples


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def summarize_watchdog(samples: list[WatchdogSample]) -> dict[str, Any]:
    def ages(name: str) -> list[int]:
        return [int(getattr(sample, name)) for sample in samples]

    summary: dict[str, Any] = {
        "sample_count": len(samples),
        "unhealthy_count": sum(not sample.healthy for sample in samples),
        "suppressed_count": sum(sample.suppressed for sample in samples),
        "reason_count": sum(sample.reasons != "none" for sample in samples),
        "action_count": sum(sample.action != "none" for sample in samples),
        "service_pids": sorted({sample.service_pid for sample in samples}),
    }
    if samples:
        summary.update(
            {
                "first_ts": samples[0].timestamp,
                "last_ts": samples[-1].timestamp,
                "cadence_coverage": round(
                    min(
                        1.0,
                        len(samples)
                        / max(
                            1,
                            math.floor(
                                (samples[-1].timestamp - samples[0].timestamp) / 60
                            )
                            + 1,
                        ),
                    ),
                    3,
                ),
            }
        )
    for name in ("tick_age", "poller_age", "sender_age"):
        values = ages(name)
        summary[name] = {
            "median": round(float(statistics.median(values)), 1) if values else None,
            "p95": _percentile(values, 0.95),
            "p99": _percentile(values, 0.99),
            "max": max(values) if values else None,
        }
    return summary


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sqlite_observation(path: Path, *, since_ts: float) -> dict[str, Any]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        counts = {}
        for table, column in (
            ("telemetry_samples", "observed_ts"),
            ("operational_events", "occurred_ts"),
            ("reboot_decisions", "evaluated_ts"),
            ("firmware_events", "collected_ts"),
            ("collector_runs", "completed_ts"),
        ):
            counts[table] = int(
                connection.execute(
                    f"SELECT count(*) FROM {table} WHERE {column} >= ?", (since_ts,)
                ).fetchone()[0]
            )
        action_decisions = int(
            connection.execute(
                """
                SELECT count(*) FROM reboot_decisions
                WHERE evaluated_ts >= ? AND result IN ('executed', 'failed')
                """,
                (since_ts,),
            ).fetchone()[0]
        )
        automatic_actions = int(
            connection.execute(
                """
                SELECT count(*) FROM operational_events
                WHERE occurred_ts >= ? AND action_source = 'auto'
                """,
                (since_ts,),
            ).fetchone()[0]
        )
        latest_samples = [
            dict(row)
            for row in connection.execute(
                """
                SELECT miner_name, state, responded, round(rate_ths, 2) AS rate_ths,
                       observed_ts
                FROM telemetry_samples
                WHERE id IN (SELECT max(id) FROM telemetry_samples GROUP BY miner_key)
                ORDER BY miner_name
                """
            ).fetchall()
        ]
        collector_row = connection.execute(
            """
            SELECT status, attempted, succeeded, failed, events_inserted, completed_ts
            FROM collector_runs ORDER BY completed_ts DESC LIMIT 1
            """
        ).fetchone()
        latest_sample_ts = max(
            (float(row["observed_ts"]) for row in latest_samples), default=None
        )
        return {
            "counts_since_start": counts,
            "action_decisions": action_decisions,
            "automatic_action_events": automatic_actions,
            "latest_samples": latest_samples,
            "latest_sample_ts": latest_sample_ts,
            "latest_collector": dict(collector_row) if collector_row else None,
        }
    finally:
        connection.close()


def evaluate(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    elapsed = float(report["observation"]["elapsed_seconds"])
    required = float(report["observation"]["required_seconds"])
    if elapsed < required:
        failures.append("observation_window_incomplete")
    if not report["service"]["running"]:
        failures.append("service_not_running")
    heartbeat = report["heartbeat"]
    thresholds = report["thresholds"]
    if heartbeat.get("schema_version") != 1:
        failures.append("heartbeat_schema_unsupported")
    if not isinstance(heartbeat.get("pid"), int) or heartbeat["pid"] <= 0:
        failures.append("heartbeat_process_missing")
    for name, limit, stale_reason in (
        ("tick_age_seconds", thresholds["tick_stale_seconds"], "tick_stale"),
        ("poller_age_seconds", thresholds["worker_stale_seconds"], "telegram_poller_stale"),
        ("sender_age_seconds", thresholds["worker_stale_seconds"], "telegram_sender_stale"),
    ):
        age = float(heartbeat[name])
        if age < -thresholds["clock_skew_tolerance_seconds"]:
            failures.append(f"{name.removesuffix('_age_seconds')}_clock_skew")
        elif age > limit:
            failures.append(stale_reason)
    collector_age = heartbeat.get("collector_age_seconds")
    if collector_age is not None:
        if collector_age < -thresholds["clock_skew_tolerance_seconds"]:
            failures.append("collector_clock_skew")
        elif collector_age > thresholds["collector_stale_seconds"]:
            failures.append("collector_stale")
    watchdog = report["watchdog"]
    if watchdog["sample_count"] == 0:
        failures.append("watchdog_samples_missing")
    if watchdog["unhealthy_count"]:
        failures.append("watchdog_unhealthy_observed")
    if watchdog["reason_count"]:
        failures.append("watchdog_reason_observed")
    if watchdog["action_count"]:
        failures.append("watchdog_action_observed")
    if watchdog.get("cadence_coverage", 0) < 0.9:
        failures.append("watchdog_cadence_incomplete")
    if watchdog.get("head_delay_seconds", math.inf) > thresholds["worker_stale_seconds"]:
        failures.append("watchdog_observation_started_late")
    if watchdog.get("tail_age_seconds", math.inf) > thresholds["worker_stale_seconds"]:
        failures.append("watchdog_tail_stale")
    if watchdog.get("service_pids") != [report["service"].get("pid")]:
        failures.append("watchdog_service_pid_changed")
    state = report["watchdog_state"]
    if state.get("is_open"):
        failures.append("watchdog_incident_open")
    database = report["database"]
    if database["action_decisions"]:
        failures.append("auto_reboot_decision_observed")
    if database["automatic_action_events"]:
        failures.append("automatic_action_event_observed")
    if database["latest_sample_age_seconds"] is None:
        failures.append("telemetry_samples_missing")
    elif database["latest_sample_age_seconds"] > thresholds["telemetry_sample_stale_seconds"]:
        failures.append("telemetry_samples_stale")
    latest_collector = database.get("latest_collector")
    if latest_collector is None:
        failures.append("collector_runs_missing")
    elif latest_collector.get("status") != "ok" or int(latest_collector.get("failed", 0)):
        failures.append("collector_latest_run_failed")
    return failures


def build_report(
    *,
    stage: str,
    since_ts: float,
    now_ts: float,
    root: Path,
    config_path: Path,
) -> dict[str, Any]:
    config = load_json(config_path)
    liveness = config.get("liveness", {})
    if not isinstance(liveness, dict):
        liveness = {}
    thresholds = {
        "tick_stale_seconds": float(liveness.get("tick_stale_seconds", 120)),
        "worker_stale_seconds": float(liveness.get("worker_stale_seconds", 120)),
        "collector_stale_seconds": float(liveness.get("collector_stale_seconds", 7200)),
        "clock_skew_tolerance_seconds": float(
            liveness.get("clock_skew_tolerance_seconds", 5)
        ),
        "telemetry_sample_stale_seconds": float(
            max(120, 2 * int(config.get("telemetry_sample_seconds", 300)))
        ),
    }
    heartbeat_path = root / str(liveness.get("heartbeat_path", "data/monitor_heartbeat.json"))
    watchdog_path = root / str(liveness.get("watchdog_log_path", "logs/watchdog.log"))
    state_path = root / str(liveness.get("watchdog_state_path", "data/watchdog_state.json"))
    heartbeat_raw = load_json(heartbeat_path)
    watchdog_samples = parse_watchdog_lines(
        watchdog_path.read_text(encoding="utf-8-sig").splitlines(), since_ts=since_ts
    )
    service_name = str(liveness.get("service_name", "MinerAlerts"))
    service_process = subprocess.run(
        ["sc.exe", "queryex", service_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    service_running, service_pid = parse_service_query(
        service_process.stdout + service_process.stderr
    )
    database = sqlite_observation(root / "data" / "miner_alerts.db", since_ts=since_ts)
    latest_sample_ts = database.pop("latest_sample_ts")
    database["latest_sample_age_seconds"] = (
        round(now_ts - latest_sample_ts, 3) if latest_sample_ts is not None else None
    )
    watchdog_summary = summarize_watchdog(watchdog_samples)
    if watchdog_samples:
        watchdog_summary["head_delay_seconds"] = round(
            max(0.0, watchdog_samples[0].timestamp - since_ts), 3
        )
        watchdog_summary["tail_age_seconds"] = round(
            max(0.0, now_ts - watchdog_samples[-1].timestamp), 3
        )
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_ts": now_ts,
        "stage": stage,
        "observation": {
            "since_ts": since_ts,
            "elapsed_seconds": max(0.0, now_ts - since_ts),
            "required_seconds": STAGE_SECONDS[stage],
        },
        "thresholds": thresholds,
        "service": {
            "name": service_name,
            "running": service_running,
            "pid": service_pid,
            "query_returncode": service_process.returncode,
        },
        "heartbeat": {
            "schema_version": heartbeat_raw.get("schema_version"),
            "pid": heartbeat_raw.get("pid"),
            "tick_sequence": heartbeat_raw.get("tick_sequence"),
            "tick_age_seconds": round(now_ts - float(heartbeat_raw["last_tick_completed_ts"]), 3),
            "poller_age_seconds": round(now_ts - float(heartbeat_raw["telegram_poller_ts"]), 3),
            "sender_age_seconds": round(now_ts - float(heartbeat_raw["telegram_sender_ts"]), 3),
            "queue_depth": heartbeat_raw.get("queue_depth"),
            "collector_age_seconds": heartbeat_raw.get("collector_age_seconds"),
        },
        "watchdog": watchdog_summary,
        "watchdog_state": load_json(state_path),
        "database": database,
    }
    report["failures"] = evaluate(report)
    report["passed"] = not report["failures"]
    return report


def emit_report(report: dict[str, Any], *, output: str | None) -> None:
    rendered = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True)
    if output:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(STAGE_SECONDS), required=True)
    parser.add_argument("--since", required=True, help="ISO-8601 observation start")
    parser.add_argument("--config", default="app/config.json")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    now_ts = time.time()
    try:
        report = build_report(
            stage=args.stage,
            since_ts=parse_timestamp(args.since),
            now_ts=now_ts,
            root=ROOT,
            config_path=config_path,
        )
    except Exception as exc:
        report = {
            "schema_version": 1,
            "generated_ts": now_ts,
            "stage": args.stage,
            "observation": {"since": args.since},
            "passed": False,
            "failures": ["observer_exception"],
            "error_type": type(exc).__name__,
        }
    emit_report(report, output=args.output)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
