#!/usr/bin/env python3
"""Unified remote server & auto-refresher for Miner Alerts UI (Dashboard & Metrics).

Binds HTTP to 0.0.0.0:8080 to serve the HTML Operations Dashboard to any device
(phone, tablet, remote PC) on the local LAN.
Periodically refreshes:
1. diagnostics/index.html & diagnostics/operations_dashboard.html (every 30s)
2. diagnostics/metrics/current.json (every 15s for Prometheus & Grafana)
"""

from __future__ import annotations

import argparse
import functools
import http.server
import logging
import os
import sys
import threading
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.metrics_sync import sync_metrics_snapshot
from tools.operations_dashboard import generate_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [UI_SERVER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("serve_monitor_ui")


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Mutes standard access logs to avoid polluting production logs."""

    def log_message(self, format, *args):
        # Only log 4xx and 5xx errors
        if len(args) >= 2 and str(args[1]).startswith(("4", "5")):
            logger.warning("%s - %s", self.address_string(), format % args)


def refresh_worker(
    db_path: Path,
    diagnostics_dir: Path,
    interval_seconds: float = 20.0,
    stop_event: threading.Event | None = None,
):
    """Background worker that keeps HTML dashboard and Prometheus snapshot fresh."""
    logger.info("Background refresh worker started (interval=%.1fs)", interval_seconds)
    index_html = diagnostics_dir / "index.html"
    ops_html = diagnostics_dir / "operations_dashboard.html"
    metrics_json = diagnostics_dir / "metrics" / "current.json"

    while stop_event is None or not stop_event.is_set():
        # 1. Sync Prometheus metrics snapshot
        try:
            sync_metrics_snapshot(
                db_path=db_path,
                target_path=metrics_json,
            )
        except Exception as exc:
            logger.warning("Metrics sync error: %s", exc)

        # 2. Regenerate HTML dashboard
        try:
            generate_dashboard(
                db_path=db_path,
                output_path=index_html,
                hours=24.0,
            )
            if ops_html != index_html:
                generate_dashboard(
                    db_path=db_path,
                    output_path=ops_html,
                    hours=24.0,
                )
        except Exception as exc:
            logger.warning("Dashboard generation error: %s", exc)

        if stop_event:
            stop_event.wait(interval_seconds)
        else:
            time.sleep(interval_seconds)


def run_ui_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    diagnostics_dir: Path | None = None,
    db_path: Path | None = None,
    refresh_interval: float = 20.0,
):
    if diagnostics_dir is None:
        diagnostics_dir = _PROJECT_ROOT / "diagnostics"
    if db_path is None:
        db_path = _PROJECT_ROOT / "data" / "miner_alerts.db"

    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / "metrics").mkdir(parents=True, exist_ok=True)

    # Perform initial render before starting HTTP server
    logger.info("Running initial render of dashboard and metrics snapshot...")
    try:
        sync_metrics_snapshot(db_path=db_path, target_path=diagnostics_dir / "metrics" / "current.json")
        generate_dashboard(db_path=db_path, output_path=diagnostics_dir / "index.html", hours=24.0)
        generate_dashboard(db_path=db_path, output_path=diagnostics_dir / "operations_dashboard.html", hours=24.0)
        logger.info("Initial render complete.")
    except Exception as exc:
        logger.error("Initial render failed: %s", exc)

    # Start background refresh thread
    stop_event = threading.Event()
    worker_thread = threading.Thread(
        target=refresh_worker,
        args=(db_path, diagnostics_dir, refresh_interval, stop_event),
        daemon=True,
    )
    worker_thread.start()

    # Configure and start HTTP server
    handler_class = functools.partial(QuietHTTPRequestHandler, directory=str(diagnostics_dir))
    server = http.server.ThreadingHTTPServer((host, port), handler_class)
    logger.info("Remote UI server listening on http://%s:%d/ (directory=%s)", host, port, diagnostics_dir)
    logger.info("Access from LAN: http://<LAN_IP>:%d/ (e.g. http://192.168.100.22:%d/)", port, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down UI server...")
    finally:
        stop_event.set()
        server.server_close()
        logger.info("UI server stopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Miner Alerts remote UI and sync metrics")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port to listen on (default 8080)")
    parser.add_argument("--interval", type=float, default=20.0, help="Refresh interval in seconds (default 20.0)")
    args = parser.parse_args()

    run_ui_server(host=args.host, port=args.port, refresh_interval=args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
