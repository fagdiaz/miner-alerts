from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.acquisition import (
    Api4028Transport,
    MinerEndpoint,
    TransportAdapter,
    TransportOutcome,
    TransportStatus,
)


def build_sanitized_endpoints(config: Mapping[str, Any]) -> tuple[MinerEndpoint, ...]:
    endpoints: list[MinerEndpoint] = []
    miners = config.get("miners")
    if not isinstance(miners, list):
        return ()
    for item in miners:
        if not isinstance(item, dict):
            continue
        host = item.get("host")
        port = item.get("port", 4028)
        if not isinstance(host, str) or not host.strip():
            continue
        if type(port) is not int or not 1 <= port <= 65535:
            continue
        endpoints.append(
            MinerEndpoint(
                key=f"miner-{len(endpoints) + 1}",
                host=host.strip(),
                port=port,
            )
        )
    return tuple(endpoints)


def nearest_rank_percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be in (0, 1]")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(quantile * len(ordered)))
    return ordered[rank - 1]


def _latency_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    finite = [max(0.0, float(value)) for value in values if math.isfinite(value)]
    if not finite:
        return {"count": 0, "min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "count": len(finite),
        "min": round(min(finite), 3),
        "p50": round(nearest_rank_percentile(finite, 0.50), 3),
        "p95": round(nearest_rank_percentile(finite, 0.95), 3),
        "max": round(max(finite), 3),
        "mean": round(statistics.fmean(finite), 3),
    }


def _summary_responded(outcome: TransportOutcome) -> bool:
    if outcome.status is not TransportStatus.SUCCESS:
        return False
    payload = outcome.payload
    if not isinstance(payload, dict):
        return False
    summary = payload.get("SUMMARY")
    return isinstance(summary, list) and bool(summary) and isinstance(summary[0], dict)


def run_sequential_baseline(
    endpoints: Iterable[MinerEndpoint],
    *,
    transport: TransportAdapter,
    samples: int,
    timeout_seconds: float,
    poll_seconds: float,
    pause_seconds: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    captured_ts: float | None = None,
) -> dict[str, Any]:
    ordered = tuple(endpoints)
    if not ordered:
        raise ValueError("at least one valid miner is required")
    if not 1 <= samples <= 20:
        raise ValueError("samples must be between 1 and 20")
    if not 1.0 <= timeout_seconds <= 10.0:
        raise ValueError("timeout_seconds must be between 1 and 10")
    if not 0.0 <= pause_seconds <= 30.0:
        raise ValueError("pause_seconds must be between 0 and 30")
    if not 1.0 <= poll_seconds <= 3600.0:
        raise ValueError("poll_seconds must be between 1 and 3600")

    per_miner: dict[str, dict[str, Any]] = {
        endpoint.key: {
            "summary_requests": 0,
            "stats_requests": 0,
            "summary_status_counts": Counter(),
            "stats_status_counts": Counter(),
            "summary_latencies_ms": [],
            "stats_latencies_ms": [],
        }
        for endpoint in ordered
    }
    cycle_latencies_ms: list[float] = []

    for sample_index in range(samples):
        cycle_started = clock()
        for endpoint in ordered:
            evidence = per_miner[endpoint.key]
            summary = transport(endpoint, "summary", timeout_seconds)
            evidence["summary_requests"] += 1
            evidence["summary_status_counts"][summary.status.value] += 1
            evidence["summary_latencies_ms"].append(summary.latency_ms)
            if _summary_responded(summary):
                stats = transport(endpoint, "stats", timeout_seconds)
                evidence["stats_requests"] += 1
                evidence["stats_status_counts"][stats.status.value] += 1
                evidence["stats_latencies_ms"].append(stats.latency_ms)
        cycle_latencies_ms.append(max(0.0, (clock() - cycle_started) * 1000.0))
        if sample_index + 1 < samples and pause_seconds:
            sleep(pause_seconds)

    rendered_miners: dict[str, dict[str, Any]] = {}
    for key, evidence in per_miner.items():
        rendered_miners[key] = {
            "summary_requests": evidence["summary_requests"],
            "stats_requests": evidence["stats_requests"],
            "summary_status_counts": dict(evidence["summary_status_counts"]),
            "stats_status_counts": dict(evidence["stats_status_counts"]),
            "summary_latency_ms": _latency_summary(evidence["summary_latencies_ms"]),
            "stats_latency_ms": _latency_summary(evidence["stats_latencies_ms"]),
        }

    cycle_summary = _latency_summary(cycle_latencies_ms)
    summary_attempts = sum(
        item["summary_requests"] for item in rendered_miners.values()
    )
    summary_successes = sum(
        item["summary_status_counts"].get(TransportStatus.SUCCESS.value, 0)
        for item in rendered_miners.values()
    )
    if summary_successes == summary_attempts:
        capture_status = "ok"
    elif summary_successes:
        capture_status = "partial"
    else:
        capture_status = "failed"
    return {
        "schema_version": 1,
        "captured_ts": float(time.time() if captured_ts is None else captured_ts),
        "mode": "sequential_read_only",
        "capture_status": capture_status,
        "samples": samples,
        "miner_count": len(ordered),
        "timeout_seconds": float(timeout_seconds),
        "poll_seconds": float(poll_seconds),
        "pause_seconds": float(pause_seconds),
        "request_order": ["summary", "stats_if_summary_responded"],
        "request_totals": {
            "summary": summary_attempts,
            "stats": sum(item["stats_requests"] for item in rendered_miners.values()),
            "automatic_retries": 0,
        },
        "cycle_latency_ms": cycle_summary,
        "effective_interval_estimate_ms": {
            "p50": round(cycle_summary["p50"] + poll_seconds * 1000.0, 3),
            "p95": round(cycle_summary["p95"] + poll_seconds * 1000.0, 3),
        },
        "miners": rendered_miners,
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a sanitized read-only sequential API 4028 baseline."
    )
    parser.add_argument("--config", default="app/config.json")
    parser.add_argument("--output", default="artifacts/spec022-sequential-baseline.json")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config_path = Path(args.config).resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"BASELINE_ERROR config_read_failed type={type(exc).__name__}", file=sys.stderr)
        return 2
    if not isinstance(config, dict):
        print("BASELINE_ERROR config_root_invalid", file=sys.stderr)
        return 2
    endpoints = build_sanitized_endpoints(config)
    if not endpoints:
        print("BASELINE_ERROR no_valid_miners", file=sys.stderr)
        return 2
    poll_seconds = config.get("poll_seconds", 30)
    try:
        poll_seconds = float(poll_seconds)
    except (TypeError, ValueError, OverflowError):
        poll_seconds = 30.0

    if args.dry_run:
        print(
            "BASELINE_DRY_RUN "
            f"miners={len(endpoints)} samples={args.samples} "
            f"timeout_seconds={args.timeout_seconds} pause_seconds={args.pause_seconds}"
        )
        return 0
    try:
        report = run_sequential_baseline(
            endpoints,
            transport=Api4028Transport(),
            samples=args.samples,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=poll_seconds,
            pause_seconds=args.pause_seconds,
        )
        output_path = Path(args.output).resolve()
        write_json_atomic(output_path, report)
    except (OSError, ValueError) as exc:
        print(f"BASELINE_ERROR capture_failed type={type(exc).__name__}", file=sys.stderr)
        return 2
    prefix = {
        "ok": "BASELINE_OK",
        "partial": "BASELINE_PARTIAL",
        "failed": "BASELINE_FAILED",
    }[report["capture_status"]]
    print(
        f"{prefix} "
        f"samples={report['samples']} miners={report['miner_count']} "
        f"summary={report['request_totals']['summary']} "
        f"stats={report['request_totals']['stats']} "
        f"cycle_p50_ms={report['cycle_latency_ms']['p50']} "
        f"cycle_p95_ms={report['cycle_latency_ms']['p95']}"
    )
    return 0 if report["capture_status"] == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
