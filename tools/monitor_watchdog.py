"""Independent, read-only liveness watchdog for the MinerAlerts service."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.liveness import (  # noqa: E402
    MaintenanceLease,
    assess_liveness,
    decide_notification,
    load_heartbeat,
    load_incident_state,
    load_maintenance_lease,
    render_liveness_assessment,
    write_incident_state,
    write_maintenance_lease,
)


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MinerAlerts liveness")
    parser.add_argument("--config", default=str(ROOT / "app" / "config.json"))
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--maintenance-seconds", type=int, default=0)
    parser.add_argument("--maintenance-reason", default="operator maintenance")
    parser.add_argument("--clear-maintenance", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        _fallback_log(f"WATCHDOG config_error type={type(exc).__name__}")
        return 1
    if not isinstance(config, dict):
        _fallback_log("WATCHDOG config_error type=invalid_root")
        return 1

    cfg = config.get("liveness", {})
    if not isinstance(cfg, dict):
        cfg = {}
    paths = _resolve_paths(cfg)
    log_path = paths["log"]
    maintenance_path = paths["maintenance"]

    if args.clear_maintenance:
        maintenance_path.unlink(missing_ok=True)
        _append_log(log_path, "WATCHDOG maintenance_cleared")
        return 0
    if args.maintenance_seconds > 0:
        max_seconds = max(60, min(86_400, int(cfg.get("maintenance_max_seconds", 3600))))
        duration = min(max_seconds, max(1, args.maintenance_seconds))
        lease = MaintenanceLease(
            expires_ts=time.time() + duration,
            reason=str(args.maintenance_reason)[:120],
        )
        write_maintenance_lease(maintenance_path, lease)
        _append_log(
            log_path,
            f"WATCHDOG maintenance_set duration_s={duration} expires_ts={int(lease.expires_ts)}",
        )
        return 0

    now_ts = time.time()
    heartbeat, heartbeat_error = load_heartbeat(paths["heartbeat"])
    service_name = str(cfg.get("service_name", "MinerAlerts"))
    service_state, service_pid = query_service(service_name)
    process_alive = bool(heartbeat and process_exists(heartbeat.pid))
    maintenance = load_maintenance_lease(maintenance_path)
    assessment = assess_liveness(
        now_ts=now_ts,
        heartbeat=heartbeat,
        heartbeat_error=heartbeat_error,
        service_state=service_state,
        process_alive=process_alive,
        tick_stale_seconds=_bounded_float(cfg, "tick_stale_seconds", 120, 30, 3600),
        worker_stale_seconds=_bounded_float(
            cfg, "worker_stale_seconds", 120, 30, 3600
        ),
        collector_stale_seconds=_bounded_float(
            cfg, "collector_stale_seconds", 7200, 300, 86_400
        ),
        clock_skew_tolerance_seconds=_bounded_float(
            cfg, "clock_skew_tolerance_seconds", 5, 0, 300
        ),
        maintenance=maintenance,
    )
    state = load_incident_state(paths["state"])
    schedule = _reminder_schedule(cfg.get("reminder_schedule_seconds"))
    action, new_state = decide_notification(
        assessment,
        state,
        now_ts=now_ts,
        reminder_schedule_seconds=schedule,
    )
    evidence = assessment.evidence
    _append_log(
        log_path,
        "WATCHDOG assessment "
        f"healthy={str(assessment.healthy).lower()} "
        f"suppressed={str(assessment.suppressed).lower()} "
        f"reasons={','.join(assessment.reason_codes) or 'none'} "
        f"service={service_state} service_pid={service_pid or 0} "
        f"tick_age={_display_age(evidence.get('tick_age_seconds'))} "
        f"poller_age={_display_age(evidence.get('telegram_poller_age_seconds'))} "
        f"sender_age={_display_age(evidence.get('telegram_sender_age_seconds'))} "
        f"action={action}",
    )

    if action != "none" and not args.no_notify:
        message = render_liveness_assessment(assessment, event=action)
        sent = send_notification(config, message, log_path=log_path, event=action)
        _append_log(
            log_path,
            f"WATCHDOG notification event={action} sent={str(sent).lower()}",
        )
        if not sent:
            new_state = state
    if not args.no_notify:
        write_incident_state(paths["state"], new_state)
    return 0


def query_service(service_name: str) -> tuple[str, Optional[int]]:
    try:
        result = subprocess.run(
            ["sc.exe", "queryex", service_name],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return "unknown", None
    if result.returncode != 0:
        return "missing", None
    output = result.stdout or ""
    state_match = re.search(r"(?:STATE|ESTADO)\s*:\s*\d+\s+([A-Z_]+)", output, re.I)
    pid_match = re.search(r"PID\s*:\s*(\d+)", output, re.I)
    state = state_match.group(1).lower() if state_match else "unknown"
    pid = int(pid_match.group(1)) if pid_match else None
    return state, pid


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information, False, int(pid)
    )
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def send_notification(
    config: dict[str, Any],
    message: str,
    *,
    log_path: Path,
    event: str,
) -> bool:
    telegram = config.get("telegram", {})
    if not isinstance(telegram, dict):
        telegram = {}
    token = str(telegram.get("bot_token") or "")
    chat_id = str(telegram.get("chat_id") or "")
    if not token or not chat_id:
        _append_log(log_path, f"WATCHDOG send_error event={event} reason=missing_config")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message[:3900],
                "disable_web_page_preview": True,
            },
            timeout=(2.0, 6.0),
        )
    except Exception as exc:
        safe = str(exc).replace(token, "<redacted>").replace("\n", " ")[:200]
        _append_log(
            log_path,
            f"WATCHDOG send_error event={event} type={type(exc).__name__} detail={safe}",
        )
        return False
    if response.status_code != 200:
        body = (response.text or "").replace(token, "<redacted>").replace("\n", " ")[:200]
        _append_log(
            log_path,
            f"WATCHDOG send_error event={event} http={response.status_code} body={body}",
        )
        return False
    return True


def _resolve_paths(config: dict[str, Any]) -> dict[str, Path]:
    values = {
        "heartbeat": config.get("heartbeat_path", "data/monitor_heartbeat.json"),
        "state": config.get("watchdog_state_path", "data/watchdog_state.json"),
        "maintenance": config.get(
            "maintenance_path", "data/watchdog_maintenance.json"
        ),
        "log": config.get("watchdog_log_path", "logs/watchdog.log"),
    }
    paths: dict[str, Path] = {}
    for key, value in values.items():
        path = Path(str(value)).expanduser()
        paths[key] = path if path.is_absolute() else ROOT / path
    return paths


def _bounded_float(
    config: dict[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def _reminder_schedule(value: Any) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        return 300, 900, 3600
    result = []
    for item in value:
        try:
            seconds = int(item)
        except (TypeError, ValueError):
            continue
        if 60 <= seconds <= 86_400:
            result.append(seconds)
    return tuple(sorted(set(result))) or (300, 900, 3600)


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _fallback_log(message: str) -> None:
    try:
        _append_log(ROOT / "logs" / "watchdog.log", message)
    except OSError:
        pass


def _display_age(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
