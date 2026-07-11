#!/usr/bin/env python3
"""
Read-only miner diagnostics collector.

The tool queries ASIC API 4028 commands and writes sanitized evidence files.
It never calls Hashcore Toolkit, never changes miner settings, and never writes
to app/state.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


COMMANDS = ("summary", "stats", "pools", "version")
SENSITIVE_KEY_PARTS = ("token", "password", "passwd", "pass", "secret", "chat_id", "bot_token")
FIELD_KEYWORDS = (
    "volt",
    "voltage",
    "power",
    "watt",
    "freq",
    "frequency",
    "fan",
    "temp",
    "chain",
    "asic",
    "error",
    "hw",
    "reject",
    "stale",
    "psu",
)
POWER_KEYWORDS = ("volt", "voltage", "vol", "power", "watt", "psu", "consumption")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"Config not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("Config root must be an object")
    return data


def miner_id(miner: dict[str, Any]) -> str:
    return str(miner.get("id") or miner.get("name") or miner.get("host") or "unknown")


def read_command(host: str, port: int, command: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload)
            chunks: list[bytes] = []
            while True:
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    raw = b"".join(chunks).replace(b"\x00", b"")
    if not raw:
        return None, "empty response"

    try:
        parsed = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as exc:
        return None, f"json parse error: {type(exc).__name__}: {exc}"

    if not isinstance(parsed, dict):
        return None, "response root is not an object"
    return parsed, None


def first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        return {}
    return value if isinstance(value, dict) else {}


def list_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def rate_from_summary(summary_entry: dict[str, Any]) -> float | None:
    candidates = (
        ("GHS 5s", 1_000.0),
        ("GHS av", 1_000.0),
        ("MHS 5s", 1_000_000.0),
        ("MHS av", 1_000_000.0),
    )
    for key, divisor in candidates:
        if key not in summary_entry:
            continue
        try:
            return round(float(summary_entry[key]) / divisor, 3)
        except (TypeError, ValueError):
            continue
    return None


def elapsed_from_summary(summary_entry: dict[str, Any]) -> int | None:
    try:
        return int(summary_entry.get("Elapsed"))
    except (TypeError, ValueError):
        return None


def count_active_boards(stats_entry: dict[str, Any]) -> int | None:
    chain_acn = stats_entry.get("chain_acn")
    if isinstance(chain_acn, list):
        return sum(1 for value in chain_acn if isinstance(value, (int, float)) and value > 0)

    count = 0
    found = False
    for index in range(0, 10):
        key_num = f"chain{index}_asicnum"
        key_alive = f"chain{index}_alive"
        key_status = f"chain{index}_status"
        key_acn = f"chain_acn{index}"
        if key_num in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_num, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_alive in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_alive, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass
            continue
        if key_status in stats_entry:
            found = True
            if str(stats_entry.get(key_status, "")).lower() in ("alive", "o", "ok"):
                count += 1
            continue
        if key_acn in stats_entry:
            found = True
            try:
                if int(stats_entry.get(key_acn, 0)) > 0:
                    count += 1
            except (TypeError, ValueError):
                pass

    return count if found else None


def extract_temperatures(items: Iterable[dict[str, Any]]) -> list[float]:
    temps: list[float] = []
    for item in items:
        for key, value in item.items():
            if "temp" not in str(key).lower():
                continue
            try:
                temp = float(value)
            except (TypeError, ValueError):
                continue
            if 0 < temp < 250:
                temps.append(round(temp, 1))
    return sorted(set(temps))


def firmware_hint(version_entry: dict[str, Any]) -> str:
    text = " ".join(str(value) for value in version_entry.values()).lower()
    if "vnish" in text:
        return "vnish"
    if "asic.to" in text or "asicto" in text:
        return "asic.to"
    if "braiins" in text:
        return "braiins"
    if "hive" in text:
        return "hiveon"
    return "unknown"


def redact_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if any(part in key_lower for part in SENSITIVE_KEY_PARTS):
        return "<redacted>"
    if key_lower == "user" and value not in (None, ""):
        digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]
        return f"<redacted:{digest}>"
    return value


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize(redact_value(str(k), v)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def collect_candidate_fields(value: Any, prefix: str = "") -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            key_lower = str(key).lower()
            if any(word in key_lower for word in FIELD_KEYWORDS):
                fields[path] = sanitize(item)
            fields.update(collect_candidate_fields(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:20]):
            fields.update(collect_candidate_fields(item, f"{prefix}[{index}]"))
    return fields


def pool_summary(raw_pools: dict[str, Any] | None) -> list[dict[str, Any]]:
    pools = list_dicts((raw_pools or {}).get("POOLS"))
    out: list[dict[str, Any]] = []
    for pool in pools:
        out.append(
            {
                "url": pool.get("URL") or pool.get("Url") or pool.get("url"),
                "status": pool.get("Status") or pool.get("STATUS") or pool.get("status"),
                "priority": pool.get("Priority") or pool.get("POOL"),
                "user": redact_value("User", pool.get("User") or pool.get("user")),
            }
        )
    return out


def collect_miner(
    miner: dict[str, Any],
    *,
    timeout: float,
    dry_run: bool,
    include_raw: bool,
) -> dict[str, Any]:
    name = str(miner.get("name") or miner.get("id") or miner.get("host") or "unknown")
    host = str(miner.get("host") or "")
    port = int(miner.get("port") or 4028)
    result: dict[str, Any] = {
        "id": miner_id(miner),
        "name": name,
        "host": host,
        "port": port,
        "responded": False,
        "dry_run": dry_run,
        "errors": {},
    }

    if dry_run:
        result["status"] = "SKIPPED_DRY_RUN"
        result["firmware_hint"] = "unknown"
        result["power_telemetry"] = {"available": False, "fields": []}
        return result

    raw: dict[str, Any] = {}
    for command in COMMANDS:
        response, error = read_command(host, port, command, timeout)
        if response is not None:
            raw[command] = response
        if error:
            result["errors"][command] = error

    summary_entry = first_dict(raw.get("summary", {}).get("SUMMARY"))
    stats_items = list_dicts(raw.get("stats", {}).get("STATS"))
    stats_entry = stats_items[0] if stats_items else {}
    active_boards = None
    for item in stats_items:
        active_boards = count_active_boards(item)
        if active_boards is not None:
            break
    version_entry = first_dict(raw.get("version", {}).get("VERSION"))

    responded = bool(raw.get("summary") or raw.get("stats") or raw.get("pools") or raw.get("version"))
    result.update(
        {
            "responded": responded,
            "status": "RESPONDED" if responded else "NO_RESPONSE",
            "rate_ths": rate_from_summary(summary_entry),
            "elapsed_seconds": elapsed_from_summary(summary_entry),
            "active_boards": active_boards,
            "temperatures_c": extract_temperatures(stats_items),
            "pools": pool_summary(raw.get("pools")),
            "firmware_hint": firmware_hint(version_entry) if version_entry else "unknown",
            "version_fields": sanitize(version_entry),
        }
    )

    candidate_fields: dict[str, Any] = {}
    for command, response in raw.items():
        candidate_fields.update(collect_candidate_fields(response, command))
    result["candidate_fields"] = candidate_fields
    result["power_telemetry"] = {
        "available": any(any(word in key.lower() for word in POWER_KEYWORDS) for key in candidate_fields),
        "fields": [key for key in candidate_fields if any(word in key.lower() for word in POWER_KEYWORDS)],
    }
    if include_raw:
        result["raw"] = sanitize(raw)
    return result


def classify_action_hint(miner: dict[str, Any], threshold_ths: float | None, expected_boards: int | None) -> str:
    if miner.get("dry_run"):
        return "dry-run only"
    if not miner.get("responded"):
        return "observe: no response, avoid reboot until signal source is confirmed"
    rate = miner.get("rate_ths")
    active_boards = miner.get("active_boards")
    if expected_boards is not None and active_boards is not None and active_boards < expected_boards:
        return "investigate: active board count below expected"
    if threshold_ths is not None and isinstance(rate, (int, float)) and rate < threshold_ths:
        return "investigate: below threshold, require sustained evidence before action"
    if miner.get("power_telemetry", {}).get("available"):
        return "observe: power telemetry fields available for correlation"
    return "observe: no immediate action from this snapshot"


def write_outputs(snapshot: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = out_dir / "snapshot.json"
    summary_path = out_dir / "summary.md"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Miner Diagnostics Snapshot",
        "",
        f"- Generated: {snapshot['generated_at']}",
        f"- Config: {snapshot['config_path']}",
        f"- Dry run: {snapshot['dry_run']}",
        f"- Miners: {len(snapshot['miners'])}",
        "",
        "## Miner Summary",
        "",
        "| Miner | Host | Status | TH/s | Boards | Temps C | Firmware | Power Fields | Action Hint |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for miner in snapshot["miners"]:
        temps = ", ".join(str(value) for value in miner.get("temperatures_c", [])) or "N/A"
        power_fields = len(miner.get("power_telemetry", {}).get("fields", []))
        lines.append(
            "| {name} | {host}:{port} | {status} | {rate} | {boards} | {temps} | {fw} | {power} | {hint} |".format(
                name=miner.get("name"),
                host=miner.get("host"),
                port=miner.get("port"),
                status=miner.get("status"),
                rate=miner.get("rate_ths") if miner.get("rate_ths") is not None else "N/A",
                boards=miner.get("active_boards") if miner.get("active_boards") is not None else "N/A",
                temps=temps,
                fw=miner.get("firmware_hint"),
                power=power_fields,
                hint=miner.get("action_hint"),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report is read-only evidence. It does not reboot, restart, tune, or write miner state.",
            "- Power fields are firmware-exposed hints only. AC input voltage requires PSU/PDU/UPS evidence unless the firmware exposes it explicitly.",
            "- Use repeated snapshots before changing reboot policy.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    miners = config.get("miners")
    if not isinstance(miners, list):
        raise SystemExit("Config must contain a miners array")

    threshold = config.get("threshold_ths")
    expected_boards = config.get("expected_boards")
    try:
        threshold_ths = float(threshold) if threshold is not None else None
    except (TypeError, ValueError):
        threshold_ths = None
    try:
        expected_boards_int = int(expected_boards) if expected_boards is not None else None
    except (TypeError, ValueError):
        expected_boards_int = None

    collected = [
        collect_miner(miner, timeout=args.timeout, dry_run=args.dry_run, include_raw=args.include_raw)
        for miner in miners
        if isinstance(miner, dict)
    ]
    for miner in collected:
        miner["action_hint"] = classify_action_hint(miner, threshold_ths, expected_boards_int)

    return {
        "generated_at": utc_now_iso(),
        "config_path": str(config_path),
        "dry_run": args.dry_run,
        "threshold_ths": threshold_ths,
        "expected_boards": expected_boards_int,
        "miners": collected,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only ASIC diagnostics collector")
    parser.add_argument("--config", default="app/config.json", help="Path to Miner Alerts config JSON")
    parser.add_argument("--out", default="diagnostics", help="Output directory")
    parser.add_argument("--timeout", type=float, default=5.0, help="Socket timeout per ASIC command")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and write report without network calls")
    parser.add_argument("--include-raw", action="store_true", help="Include sanitized raw API responses in snapshot.json")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    snapshot = build_snapshot(args)
    out_dir = Path(args.out).resolve()
    write_outputs(snapshot, out_dir)
    print(f"Wrote diagnostics: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
