#!/usr/bin/env python3
"""Prometheus Metrics Exporter for Miner Alerts (Spec 025).

Exposes sanitized operational metrics in Prometheus exposition text format
from diagnostics/metrics/current.json without accessing the live monitor,
database, or network.
Strictly enforces:
- Zero action/mutation capabilities (pure read-only).
- 26 Prometheus metric families.
- Fixed label values from finite enums.
- Cardinality budget: 23 global series + 20 per configured miner (max 103 for 4 miners).
- Safe stale behavior: if missing, malformed or > stale_seconds, exports snapshot health only.
"""

from __future__ import annotations

import argparse
import http.server
import io
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Enable running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.metrics_snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    DEFAULT_STALE_SECONDS,
    VALID_ACQ_QUALITIES,
    VALID_COLLECTOR_STATUSES,
    VALID_MINER_STATES,
    VALID_TELEGRAM_OUTCOMES,
    MetricsSnapshot,
    load_metrics_snapshot,
)

METRIC_FAMILIES_DEF = [
    ("miner_alerts_snapshot_valid", "gauge", "1 only when current parse/schema/freshness is valid"),
    ("miner_alerts_snapshot_age_seconds", "gauge", "Age of metrics snapshot file in seconds"),
    ("miner_alerts_snapshot_schema_version", "gauge", "Supported numeric schema version"),
    ("miner_alerts_exporter_scrape_duration_seconds", "gauge", "Duration of exporter scrape in seconds"),
    ("miner_alerts_monitor_up", "gauge", "1 for a fresh valid completed-tick snapshot"),
    ("miner_alerts_monitor_process_start_time_seconds", "gauge", "Monitor process start timestamp in epoch seconds"),
    ("miner_alerts_monitor_tick_sequence_total", "counter", "Completed tick sequence count"),
    ("miner_alerts_monitor_last_tick_timestamp_seconds", "gauge", "Last completed tick timestamp in epoch seconds"),
    ("miner_alerts_telegram_poller_age_seconds", "gauge", "Age of last Telegram poller activity in seconds"),
    ("miner_alerts_telegram_sender_age_seconds", "gauge", "Age of last Telegram sender activity in seconds"),
    ("miner_alerts_telegram_queue_depth", "gauge", "Current Telegram delivery queue depth"),
    ("miner_alerts_telegram_messages_total", "counter", "Process-lifetime Telegram message delivery counts by outcome"),
    ("miner_alerts_collector_age_seconds", "gauge", "Age of last collector execution in seconds"),
    ("miner_alerts_collector_status", "gauge", "Collector status one-hot indicator"),
    ("miner_alerts_acquisition_epoch_duration_seconds", "gauge", "Latest authoritative fleet acquisition epoch duration in seconds"),
    ("miner_alerts_miner_responded", "gauge", "1 when miner authoritative signal responded"),
    ("miner_alerts_miner_rate_ths", "gauge", "Current miner hashrate in TH/s"),
    ("miner_alerts_miner_threshold_ths", "gauge", "Configured hashrate threshold in TH/s"),
    ("miner_alerts_miner_sample_age_seconds", "gauge", "Age of latest authoritative sample in seconds"),
    ("miner_alerts_miner_state", "gauge", "Miner operational state one-hot indicator"),
    ("miner_alerts_miner_active_boards", "gauge", "Number of currently active hashboards"),
    ("miner_alerts_miner_expected_boards", "gauge", "Number of expected hashboards"),
    ("miner_alerts_miner_episode_active", "gauge", "1 when irregular episode is active"),
    ("miner_alerts_miner_episode_duration_seconds", "gauge", "Duration of current active episode in seconds"),
    ("miner_alerts_miner_acquisition_quality", "gauge", "Acquisition quality one-hot indicator"),
    ("miner_alerts_miner_acquisition_latency_seconds", "gauge", "Authoritative request latency in seconds"),
]


def render_prometheus_text(
    snapshot_path: str | Path,
    stale_seconds: float = DEFAULT_STALE_SECONDS,
    now: Optional[float] = None,
) -> Tuple[str, int]:
    """Renders Prometheus plain text exposition format from snapshot.

    Returns (text_payload, total_series_count).
    """
    scrape_start = time.time()
    current_ts = now or scrape_start
    lines: List[str] = []
    total_series = 0

    is_fresh, parsed, age, reason = load_metrics_snapshot(snapshot_path, max_age_seconds=stale_seconds)

    def write_family_header(name: str, mtype: str, help_text: str):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {mtype}")

    def emit_series(name: str, value: float | int, labels: Optional[Dict[str, str]] = None):
        nonlocal total_series
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            lines.append(f"{name}{{{label_str}}} {value}")
        else:
            lines.append(f"{name} {value}")
        total_series += 1

    # Stale or invalid snapshot: export health metrics only
    if not is_fresh or parsed is None:
        write_family_header("miner_alerts_snapshot_valid", "gauge", "1 only when current parse/schema/freshness is valid")
        emit_series("miner_alerts_snapshot_valid", 0)

        if age >= 0:
            write_family_header("miner_alerts_snapshot_age_seconds", "gauge", "Age of metrics snapshot file in seconds")
            emit_series("miner_alerts_snapshot_age_seconds", round(age, 3))

        scrape_duration = time.time() - scrape_start
        write_family_header("miner_alerts_exporter_scrape_duration_seconds", "gauge", "Duration of exporter scrape in seconds")
        emit_series("miner_alerts_exporter_scrape_duration_seconds", round(scrape_duration, 4))

        return "\n".join(lines) + "\n", total_series

    # Valid & fresh snapshot
    write_family_header("miner_alerts_snapshot_valid", "gauge", "1 only when current parse/schema/freshness is valid")
    emit_series("miner_alerts_snapshot_valid", 1)

    write_family_header("miner_alerts_snapshot_age_seconds", "gauge", "Age of metrics snapshot file in seconds")
    emit_series("miner_alerts_snapshot_age_seconds", round(age, 3))

    write_family_header("miner_alerts_snapshot_schema_version", "gauge", "Supported numeric schema version")
    emit_series("miner_alerts_snapshot_schema_version", parsed.schema_version)

    write_family_header("miner_alerts_monitor_up", "gauge", "1 for a fresh valid completed-tick snapshot")
    emit_series("miner_alerts_monitor_up", 1)

    write_family_header("miner_alerts_monitor_process_start_time_seconds", "gauge", "Monitor process start timestamp in epoch seconds")
    emit_series("miner_alerts_monitor_process_start_time_seconds", round(parsed.monitor.process_start_ts, 3))

    write_family_header("miner_alerts_monitor_tick_sequence_total", "counter", "Completed tick sequence count")
    emit_series("miner_alerts_monitor_tick_sequence_total", parsed.monitor.tick_sequence)

    write_family_header("miner_alerts_monitor_last_tick_timestamp_seconds", "gauge", "Last completed tick timestamp in epoch seconds")
    emit_series("miner_alerts_monitor_last_tick_timestamp_seconds", round(parsed.monitor.last_tick_completed_ts, 3))

    if parsed.monitor.telegram_poller_ts is not None:
        poller_age = max(0.0, current_ts - parsed.monitor.telegram_poller_ts)
        write_family_header("miner_alerts_telegram_poller_age_seconds", "gauge", "Age of last Telegram poller activity in seconds")
        emit_series("miner_alerts_telegram_poller_age_seconds", round(poller_age, 3))

    if parsed.monitor.telegram_sender_ts is not None:
        sender_age = max(0.0, current_ts - parsed.monitor.telegram_sender_ts)
        write_family_header("miner_alerts_telegram_sender_age_seconds", "gauge", "Age of last Telegram sender activity in seconds")
        emit_series("miner_alerts_telegram_sender_age_seconds", round(sender_age, 3))

    write_family_header("miner_alerts_telegram_queue_depth", "gauge", "Current Telegram delivery queue depth")
    emit_series("miner_alerts_telegram_queue_depth", parsed.monitor.queue_depth)

    # Telegram messages by outcome
    write_family_header("miner_alerts_telegram_messages_total", "counter", "Process-lifetime Telegram message delivery counts by outcome")
    for outcome in sorted(list(VALID_TELEGRAM_OUTCOMES)):
        val = getattr(parsed.telegram, f"{outcome}_total", 0)
        emit_series("miner_alerts_telegram_messages_total", val, {"outcome": outcome})

    if parsed.collector.age_seconds is not None:
        write_family_header("miner_alerts_collector_age_seconds", "gauge", "Age of last collector execution in seconds")
        emit_series("miner_alerts_collector_age_seconds", round(parsed.collector.age_seconds, 3))

    write_family_header("miner_alerts_collector_status", "gauge", "Collector status one-hot indicator")
    for st in sorted(list(VALID_COLLECTOR_STATUSES)):
        emit_series("miner_alerts_collector_status", 1 if parsed.collector.status == st else 0, {"status": st})

    if parsed.acquisition.epoch_duration_seconds is not None:
        write_family_header("miner_alerts_acquisition_epoch_duration_seconds", "gauge", "Latest authoritative fleet acquisition epoch duration in seconds")
        emit_series("miner_alerts_acquisition_epoch_duration_seconds", round(parsed.acquisition.epoch_duration_seconds, 3))

    # Miner metrics
    if parsed.miners:
        write_family_header("miner_alerts_miner_responded", "gauge", "1 when miner authoritative signal responded")
        for m in parsed.miners:
            emit_series("miner_alerts_miner_responded", 1 if m.responded else 0, {"miner": m.miner_id})

        rate_miners = [m for m in parsed.miners if m.rate_ths is not None]
        if rate_miners:
            write_family_header("miner_alerts_miner_rate_ths", "gauge", "Current miner hashrate in TH/s")
            for m in rate_miners:
                emit_series("miner_alerts_miner_rate_ths", round(m.rate_ths, 2), {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_threshold_ths", "gauge", "Configured hashrate threshold in TH/s")
        for m in parsed.miners:
            emit_series("miner_alerts_miner_threshold_ths", round(m.threshold_ths, 2), {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_sample_age_seconds", "gauge", "Age of latest authoritative sample in seconds")
        for m in parsed.miners:
            m_age = max(0.0, current_ts - m.sample_ts)
            emit_series("miner_alerts_miner_sample_age_seconds", round(m_age, 3), {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_state", "gauge", "Miner operational state one-hot indicator")
        for m in parsed.miners:
            for st in sorted(list(VALID_MINER_STATES)):
                emit_series("miner_alerts_miner_state", 1 if m.state == st else 0, {"miner": m.miner_id, "state": st})

        boards_miners = [m for m in parsed.miners if m.active_boards is not None]
        if boards_miners:
            write_family_header("miner_alerts_miner_active_boards", "gauge", "Number of currently active hashboards")
            for m in boards_miners:
                emit_series("miner_alerts_miner_active_boards", m.active_boards, {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_expected_boards", "gauge", "Number of expected hashboards")
        for m in parsed.miners:
            emit_series("miner_alerts_miner_expected_boards", m.expected_boards, {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_episode_active", "gauge", "1 when irregular episode is active")
        for m in parsed.miners:
            emit_series("miner_alerts_miner_episode_active", 1 if m.episode_active else 0, {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_episode_duration_seconds", "gauge", "Duration of current active episode in seconds")
        for m in parsed.miners:
            emit_series("miner_alerts_miner_episode_duration_seconds", round(m.episode_duration_seconds, 2), {"miner": m.miner_id})

        write_family_header("miner_alerts_miner_acquisition_quality", "gauge", "Acquisition quality one-hot indicator")
        for m in parsed.miners:
            for q in sorted(list(VALID_ACQ_QUALITIES)):
                emit_series("miner_alerts_miner_acquisition_quality", 1 if m.acquisition_quality == q else 0, {"miner": m.miner_id, "quality": q})

        latency_miners = [m for m in parsed.miners if m.acquisition_latency_seconds is not None]
        if latency_miners:
            write_family_header("miner_alerts_miner_acquisition_latency_seconds", "gauge", "Authoritative request latency in seconds")
            for m in latency_miners:
                emit_series("miner_alerts_miner_acquisition_latency_seconds", round(m.acquisition_latency_seconds, 3), {"miner": m.miner_id})

    # Record scrape duration
    scrape_duration = time.time() - scrape_start
    write_family_header("miner_alerts_exporter_scrape_duration_seconds", "gauge", "Duration of exporter scrape in seconds")
    emit_series("miner_alerts_exporter_scrape_duration_seconds", round(scrape_duration, 4))

    return "\n".join(lines) + "\n", total_series


class MetricsHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler serving /metrics and /healthz."""

    snapshot_path: str = DEFAULT_SNAPSHOT_PATH
    stale_seconds: float = DEFAULT_STALE_SECONDS

    def do_GET(self):
        if self.path in ("/metrics", "/metrics/"):
            payload, count = render_prometheus_text(self.snapshot_path, self.stale_seconds)
            encoded = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        elif self.path in ("/healthz", "/live"):
            body = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Mute normal scrape logging to keep output clean
        pass


def run_exporter_server(host: str = "0.0.0.0", port: int = 9100, snapshot_path: str = DEFAULT_SNAPSHOT_PATH, stale_seconds: float = DEFAULT_STALE_SECONDS):
    handler = MetricsHTTPRequestHandler
    handler.snapshot_path = snapshot_path
    handler.stale_seconds = stale_seconds
    server = http.server.ThreadingHTTPServer((host, port), handler)
    print(f"[METRICS_EXPORTER] Listening on {host}:{port} serving {snapshot_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[METRICS_EXPORTER] Shutting down.")
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prometheus Metrics Exporter for Miner Alerts (Spec 025)")
    parser.add_argument("--snapshot-path", default=DEFAULT_SNAPSHOT_PATH, help="Path to current.json snapshot")
    parser.add_argument("--stale-seconds", type=float, default=DEFAULT_STALE_SECONDS, help="Max snapshot age before considered stale")
    parser.add_argument("--port", type=int, default=9100, help="Port to listen on (default 9100)")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to (default 0.0.0.0)")
    parser.add_argument("--dry-run", action="store_true", help="Print current metrics to stdout and exit")
    args = parser.parse_args()

    if args.dry_run:
        payload, count = render_prometheus_text(args.snapshot_path, args.stale_seconds)
        print(payload, end="")
        print(f"# Total series count: {count}", file=sys.stderr)
        return 0

    run_exporter_server(host=args.host, port=args.port, snapshot_path=args.snapshot_path, stale_seconds=args.stale_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
