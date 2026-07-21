#!/usr/bin/env python3
"""Bounded read-only Vnish log collector for the confirmed WebSocket API."""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.event_store import EventStore
from app.vnish_logs import ALLOWED_LOG_TABS, VnishLogEvent, parse_vnish_log_text


_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}$")


@dataclass(frozen=True)
class CollectionResult:
    ok: bool
    host: str
    source_tab: str
    bytes_received: int
    text: str = ""
    truncated: bool = False
    error: Optional[str] = None


def _default_connect(url: str, timeout: float):
    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError(
            "websocket-client is required; install requirements.txt"
        ) from exc
    return websocket.create_connection(
        url,
        timeout=timeout,
        enable_multithread=False,
    )


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, (TimeoutError, socket.timeout)) or "timeout" in type(exc).__name__.lower()


def collect_vnish_tab(
    host: str,
    source_tab: str,
    *,
    connect_timeout: float = 3.0,
    idle_timeout: float = 1.0,
    max_bytes: int = 1_048_576,
    connect_fn: Optional[Callable[[str, float], Any]] = None,
) -> CollectionResult:
    safe_host = str(host).strip()
    safe_tab = str(source_tab).strip().lower()
    if not _SAFE_HOST_RE.fullmatch(safe_host):
        return CollectionResult(False, safe_host[:80], safe_tab[:20], 0, error="invalid_host")
    if safe_tab not in ALLOWED_LOG_TABS:
        return CollectionResult(False, safe_host, safe_tab[:20], 0, error="invalid_tab")

    safe_connect_timeout = max(0.5, min(float(connect_timeout), 10.0))
    safe_idle_timeout = max(0.1, min(float(idle_timeout), 10.0))
    safe_max_bytes = max(4_096, min(int(max_bytes), 4_194_304))
    url = f"ws://{safe_host}/api/v1/logs-ws/{safe_tab}"
    connector = connect_fn or _default_connect
    connection = None
    chunks: list[str] = []
    received = 0
    truncated = False
    error: Optional[str] = None
    try:
        connection = connector(url, safe_connect_timeout)
        connection.settimeout(safe_idle_timeout)
        while received < safe_max_bytes:
            try:
                message = connection.recv()
            except Exception as exc:
                if _is_timeout(exc):
                    break
                error = type(exc).__name__
                break
            if message is None or message == "":
                break
            if isinstance(message, bytes):
                decoded = message.decode("utf-8", errors="replace")
            else:
                decoded = str(message)
            encoded = decoded.encode("utf-8", errors="replace")
            remaining = safe_max_bytes - received
            if len(encoded) > remaining:
                chunks.append(encoded[:remaining].decode("utf-8", errors="ignore"))
                received = safe_max_bytes
                truncated = True
                break
            chunks.append(decoded)
            received += len(encoded)
    except Exception as exc:
        error = type(exc).__name__
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    return CollectionResult(
        ok=error is None,
        host=safe_host,
        source_tab=safe_tab,
        bytes_received=received,
        text="".join(chunks),
        truncated=truncated,
        error=error,
    )


def _load_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Config root must be an object")
    return data


def _db_path(config: dict[str, Any], explicit: Optional[Path]) -> Path:
    if explicit is not None:
        path = explicit.expanduser()
    else:
        path = Path(str(config.get("event_store_path") or "data/miner_alerts.db")).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _miner_identity(miner: dict[str, Any]) -> tuple[str, str, str]:
    name = str(miner.get("name") or miner.get("id") or miner.get("host") or "unknown")
    host = str(miner.get("host") or "").strip()
    try:
        port = int(miner.get("port", 4028))
    except (TypeError, ValueError):
        port = 4028
    return f"{name}|{host}:{port}", name, host


def _store_events(
    store: EventStore,
    events: list[VnishLogEvent],
    *,
    miner_key: str,
    miner_name: str,
    host: str,
) -> tuple[int, int, int]:
    inserted = 0
    duplicates = 0
    failed = 0
    for event in events:
        result = store.record_firmware_event(
            collected_ts=event.collected_ts,
            source_ts_text=event.source_ts_text,
            miner_key=miner_key,
            miner_name=miner_name,
            host=host,
            source_tab=event.source_tab,
            source_fingerprint=event.source_fingerprint,
            category=event.category,
            severity=event.severity,
            code=event.code,
            summary=event.summary,
        )
        if result is None:
            failed += 1
        elif result == 0:
            duplicates += 1
        else:
            inserted += 1
    return inserted, duplicates, failed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "app" / "config.json")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--tabs", default="status,miner,autotune,system")
    parser.add_argument("--connect-timeout", type=float, default=3.0)
    parser.add_argument("--idle-timeout", type=float, default=1.0)
    parser.add_argument("--max-bytes", type=int, default=1_048_576)
    parser.add_argument("--max-lines", type=int, default=5_000)
    parser.add_argument("--max-events", type=int, default=1_000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    config = _load_config(args.config.resolve())
    miners = config.get("miners")
    if not isinstance(miners, list) or not miners:
        print("VNISH_LOG_COLLECTOR error=no_miners")
        return 2
    tabs = tuple(dict.fromkeys(part.strip().lower() for part in args.tabs.split(",") if part.strip()))
    invalid_tabs = [tab for tab in tabs if tab not in ALLOWED_LOG_TABS]
    if not tabs or invalid_tabs:
        print(f"VNISH_LOG_COLLECTOR error=invalid_tabs count={len(invalid_tabs)}")
        return 2

    store = None if args.dry_run else EventStore(_db_path(config, args.db))
    if store is not None and not store.available:
        print("VNISH_LOG_COLLECTOR error=event_store_unavailable")
        return 2
    failures = 0
    try:
        for miner in miners:
            if not isinstance(miner, dict):
                failures += 1
                continue
            miner_key, miner_name, host = _miner_identity(miner)
            for tab in tabs:
                collected_ts = time.time()
                result = collect_vnish_tab(
                    host,
                    tab,
                    connect_timeout=args.connect_timeout,
                    idle_timeout=args.idle_timeout,
                    max_bytes=args.max_bytes,
                )
                if not result.ok:
                    failures += 1
                    print(
                        f"VNISH_LOG miner={miner_name} tab={tab} ok=false "
                        f"bytes={result.bytes_received} error={result.error}"
                    )
                    continue
                events = parse_vnish_log_text(
                    result.text,
                    source_tab=tab,
                    collected_ts=collected_ts,
                    max_lines=args.max_lines,
                    max_events=args.max_events,
                )
                inserted = duplicates = failed = 0
                if store is not None:
                    inserted, duplicates, failed = _store_events(
                        store,
                        events,
                        miner_key=miner_key,
                        miner_name=miner_name,
                        host=host,
                    )
                    failures += failed
                print(
                    f"VNISH_LOG miner={miner_name} tab={tab} ok=true "
                    f"bytes={result.bytes_received} parsed={len(events)} "
                    f"inserted={inserted} duplicates={duplicates} failed={failed} "
                    f"truncated={str(result.truncated).lower()} dry_run={str(args.dry_run).lower()}"
                )
    finally:
        if store is not None:
            store.close()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
